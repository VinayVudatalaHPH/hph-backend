"""One-time backfill from the legacy Daily_Refresh spreadsheet pipeline into
this backend's schema (Phase 2 of the cohorts/target-config build).

Reads the same ramp workbook, manual production files, and Kairon dumps that
Daily_Refresh/build/etl.py reads (file reading is ported from that project's
build/readers.py: files are identified by what's inside them, not by name or
extension, and headers aren't assumed to be on the first row), and produces
the same stage boundaries for ramp-tracked coders except where
first_activity_date() deliberately corrects a hand-typed M1 date - every such
difference is printed for a human to review, not silently applied.

Run via: flask cohorts import-legacy-data --input /path/to/Daily_Refresh/input
"""
import datetime as dt
import os
import re

import pandas as pd

from app.cohorts.models import Coder, CoderAlias, CoderStagePeriod, Cohort, KaironCompletion, ManualProductionFact
from app.cohorts.services import first_activity_date
from app.extensions import db

# ---------------------------------------------------------------------------
# File reading, ported from Daily_Refresh/build/readers.py.
# ---------------------------------------------------------------------------
MANUAL_REQ = {"date", "coder", "production count today"}
KAIRON_REQ = {"status", "coding analyst"}
RAMP_REQ = {"ramp month", "planned time period"}


def _norm(v):
    return str(v).strip().lower().replace("\n", " ").replace(" ", " ")


def _file_kind(path):
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return None
    if head[:2] == b"PK":
        return "ods" if b"opendocument.spreadsheet" in head[:200] else "xlsx"
    if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls"
    return "text"


def _sheets(path):
    kind = _file_kind(path)
    if kind == "text":
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            for sep in (",", "\t", ";", "|"):
                try:
                    df = pd.read_csv(
                        path, header=None, dtype=str, encoding=enc, sep=sep, engine="python", on_bad_lines="skip"
                    )
                    if df.shape[1] > 1:
                        yield ("csv", df)
                        return
                except Exception:
                    continue
        return
    engine = {"ods": "odf", "xlsx": "openpyxl", "xls": None}[kind]
    try:
        xl = pd.ExcelFile(path, engine=engine)
    except Exception:
        try:
            xl = pd.ExcelFile(path)
        except Exception:
            return
    for name in xl.sheet_names:
        try:
            yield (name, pd.read_excel(xl, name, header=None))
        except Exception:
            continue


def _find_table(path, required, max_header_row=8):
    for name, raw in _sheets(path):
        if raw is None or raw.empty:
            continue
        limit = min(max_header_row, len(raw))
        for h in range(limit):
            cols = [_norm(v) for v in raw.iloc[h].tolist()]
            if not required <= set(cols):
                continue
            df = raw.iloc[h + 1 :].copy()
            df.columns = [str(v).strip() if str(v) != "nan" else f"col{i}" for i, v in enumerate(raw.iloc[h].tolist())]
            df = df.dropna(how="all").reset_index(drop=True)
            return df, name
    return None, None


def classify(path):
    if os.path.basename(path).startswith("~$"):
        return None
    for _name, raw in _sheets(path):
        if raw is None or raw.empty:
            continue
        for h in range(min(8, len(raw))):
            cols = set(_norm(v) for v in raw.iloc[h].tolist())
            if KAIRON_REQ <= cols:
                return "kairon"
            if MANUAL_REQ <= cols:
                return "manual"
            if RAMP_REQ <= cols:
                return "ramp"
    return None


def read_manual(path):
    df, _ = _find_table(path, MANUAL_REQ)
    if df is None:
        return None
    ren = {}
    for c in df.columns:
        n = _norm(c)
        if n == "date":
            ren[c] = "Date"
        elif n == "coder":
            ren[c] = "Coder"
        elif n == "production count today":
            ren[c] = "Production count today"
    df = df.rename(columns=ren)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    df["Coder"] = df["Coder"].astype(str).str.strip()
    if "Production count today" not in df.columns:
        df["Production count today"] = 0.0
    df["Production count today"] = pd.to_numeric(df["Production count today"], errors="coerce").fillna(0.0)
    df = df[df["Date"].notna() & ~df["Coder"].isin(["nan", "", "None"])]
    return df[["Date", "Coder", "Production count today"]].reset_index(drop=True)


def read_kairon(path):
    df, _ = _find_table(path, KAIRON_REQ)
    if df is None:
        return None
    ren = {}
    for c in df.columns:
        n = _norm(c)
        for want in ("mbi", "level", "status", "completed"):
            if n == want:
                ren[c] = want.title() if want != "mbi" else "MBI"
        if n == "coding analyst":
            ren[c] = "Coding Analyst"
    df = df.rename(columns=ren)
    df["Coder"] = df["Coding Analyst"].astype(str).str.replace(" - HPH Coding Analyst", "", regex=False).str.strip()
    df["Status"] = df["Status"].astype(str).str.strip()
    df["Completed"] = pd.to_datetime(df.get("Completed"), errors="coerce").dt.date
    for c in ("MBI", "Level"):
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].astype(str).str.strip()
    df = df[df["Coder"].ne("") & df["Coder"].ne("nan")]
    return df.reset_index(drop=True)


def _scan(folder):
    out = []
    if not os.path.isdir(folder):
        return out
    for root, _dirs, files in os.walk(folder):
        for f in sorted(files):
            fp = os.path.join(root, f)
            if os.path.basename(fp).startswith("~$"):
                continue
            out.append(fp)
    return sorted(out, key=os.path.getmtime)


# ---------------------------------------------------------------------------
# Ramp-workbook parsing, ported from Daily_Refresh/build/etl.py and
# build/etl_names.py.
# ---------------------------------------------------------------------------
NAME_MAP = {
    "Ajaya Mishra": "Ajaya Mishra", "Charishma": "Charishma Sonani", "Srinivas": "Srinivas Polagoni",
    "Anitha": "Anitha Sappa", "Rekha": "Rekha Samala", "Sayyed": "Sayyed Lalahmad",
    "Gnapitha": "Gnapitha Tamminana", "Susanna": "Susanna Juttiga", "Tejaswini": "Tejaswini Sunke",
    "Shahabaz": "Shahabaz Saleem", "Mayur": "Mayur Charde", "Meena": "Meena Mekala",
    "Shadab": "Shaikh Shadab", "Sravan": "Sravan Marri", "Madhu": "Madhu Derangula",
    "Rachana": "Rachana Kothi", "Vishwamithra": "Vishwamithra Dasari", "Ramadevi": "Ramadevi Rayagonda",
    "Venkatachary": "Venkatachary Mulugu", "Vijay Kumar": "Vijay Bade", "Pravallika": "Pravallika Mandapati",
    "Sreelekha": "Sreelekha Gadwala", "Asha Gorre": "Asha Gorre", "Prathyusha Puli": "Pratyusha Puli",
    "Mahesh": "Mahesh Mopuri", "Ravi": "Ravi Gollamudi", "Saranya": "Saranya Muli",
    "Spandana": "Spandana Budde", "Rajini": "Rajini Garvandula", "Ramatulasi": "Ramatulasi Vanguri",
    "Manvi": "Manvi Ghadekar", "Bhargav": "Bhargav Madem", "Bhargavi": "Bhargavi Sabbani",
    "Rathna nimmagadda": "Rathna Kumari Nimmagadda", "DivyaSri": "Divya Sri Bollam",
    "Mohan Boya": "Mohan Boya", "Prameela": "Prameela Vedulla",
}

STAGE_ORDER = ["M1", "M2", "M3", "M4", "Steady State"]
RAMP_SHEETS = ["Cohort 1", "Cohort 2", "Cohort 3"]
RAMP_HEADER_ROW = 3

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _parse_half(txt, prev_month=None):
    t = str(txt).strip().lower().replace(" ", " ")
    t = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", t)
    m = re.search(r"([a-z]+)\s*(\d{1,2})", t)
    if m and m.group(1)[:3] in MONTHS:
        return MONTHS[m.group(1)[:3]], int(m.group(2))
    m = re.search(r"(\d{1,2})\s*([a-z]+)", t)
    if m and m.group(2)[:3] in MONTHS:
        return MONTHS[m.group(2)[:3]], int(m.group(1))
    m = re.search(r"(\d{1,2})", t)
    if m and prev_month:
        return prev_month, int(m.group(1))
    return None


def _parse_period(txt, year):
    if txt is None or (isinstance(txt, float) and pd.isna(txt)):
        return None, None
    s = str(txt).strip()
    if not s or s.lower() == "nan":
        return None, None
    s = s.replace("–", "-").replace("—", "-")
    parts = [p for p in re.split(r"\s*-\s*|\s+to\s+", s) if p.strip()]
    if len(parts) < 2:
        return None, None
    a = _parse_half(parts[0])
    if a is None:
        return None, None
    b = _parse_half(parts[1], prev_month=a[0])
    if b is None:
        return None, None
    d1 = dt.date(year, a[0], a[1])
    y2 = year + 1 if b[0] < a[0] else year
    d2 = dt.date(y2, b[0], b[1])
    return d1, d2


def _get_or_create_coder(full_name, join_date, cohort_id=None):
    coder = Coder.query.filter_by(full_name=full_name).first()
    if coder is None:
        coder = Coder(full_name=full_name, join_date=join_date, cohort_id=cohort_id)
        db.session.add(coder)
        db.session.flush()
    return coder


def _upsert_manual_fact(coder_id, activity_date, count):
    fact = ManualProductionFact.query.filter_by(coder_id=coder_id, activity_date=activity_date).first()
    if fact is None:
        db.session.add(ManualProductionFact(coder_id=coder_id, activity_date=activity_date, production_count=int(count)))
    else:
        fact.production_count = int(count)


def import_legacy_data(input_dir, year=None, log=print):
    year = year or dt.date.today().year

    ramp_candidates = [f for f in _scan(os.path.join(input_dir, "ramp")) if classify(f) == "ramp"]
    if not ramp_candidates:
        raise SystemExit("No ramp workbook found in input/ramp - nothing to import.")
    ramp_path = ramp_candidates[-1]
    manual_files = [f for f in _scan(os.path.join(input_dir, "manual")) if classify(f) == "manual"]
    kairon_files = [f for f in _scan(os.path.join(input_dir, "kairon")) if classify(f) == "kairon"]
    log(f"ramp workbook: {os.path.basename(ramp_path)}")
    log(f"manual files: {[os.path.basename(f) for f in manual_files]}")
    log(f"kairon dumps: {[os.path.basename(f) for f in kairon_files]}")

    # ---- 1. Ramp workbook: per-coder stage rows + the embedded daily grid
    per_coder_rows = {}  # full_name -> [ {ramp_month, stage, actual_start, actual_end}, ... ]
    coder_sheet = {}  # full_name -> sheet index (1-based)
    sheet_planned_starts = {}  # sheet index -> [date, ...]
    old_grid_counts = {}  # full_name -> {date: count}
    alias_map = {}  # full_name -> {short names}

    for sheet_index, sheet in enumerate(RAMP_SHEETS, start=1):
        try:
            raw = pd.read_excel(ramp_path, sheet, header=None, engine="openpyxl")
        except Exception:
            log(f"sheet {sheet!r} not found in the ramp workbook - skipping")
            continue

        hdr = raw.iloc[RAMP_HEADER_ROW]
        date_cols = {
            c: pd.Timestamp(hdr[c]).date()
            for c in range(14, raw.shape[1])
            if isinstance(hdr[c], (pd.Timestamp, dt.datetime, dt.date))
        }
        body = raw.iloc[RAMP_HEADER_ROW + 1 :].copy()
        body[1] = body[1].ffill()

        for _, r in body.iterrows():
            coder_short = str(r[1]).strip() if pd.notna(r[1]) else None
            ramp = r[2]
            if coder_short is None or pd.isna(ramp):
                continue
            full_name = NAME_MAP.get(coder_short)
            if full_name is None:
                log(f"!! unmapped coder in {sheet}: {coder_short!r} - skipped")
                continue
            ramp = int(ramp)
            stage = STAGE_ORDER[min(ramp, 5) - 1]
            planned_start, planned_end = _parse_period(r[3], year)
            actual_start, actual_end = _parse_period(r[4], year)
            if actual_start is None and planned_start is not None:
                actual_start, actual_end = planned_start, planned_end

            per_coder_rows.setdefault(full_name, []).append(
                {"ramp_month": ramp, "stage": stage, "actual_start": actual_start, "actual_end": actual_end}
            )
            coder_sheet[full_name] = sheet_index
            if planned_start:
                sheet_planned_starts.setdefault(sheet_index, []).append(planned_start)
            if coder_short != full_name:
                alias_map.setdefault(full_name, set()).add(coder_short)

            for c, d in date_cols.items():
                v = r[c]
                if pd.isna(v):
                    continue
                if str(v).strip().upper() in ("B", "N", "L", "H"):
                    continue  # a downtime/leave/holiday flag, not a chart count
                try:
                    old_grid_counts.setdefault(full_name, {})[d] = float(v)
                except (TypeError, ValueError):
                    continue

    # ---- cohorts, one per sheet that actually had coders -----------------
    cohorts_by_sheet = {}
    for sheet_index, starts in sheet_planned_starts.items():
        cohort = Cohort.query.filter_by(sequence_no=sheet_index).first()
        if cohort is None:
            cohort = Cohort(sequence_no=sheet_index, label=RAMP_SHEETS[sheet_index - 1], window_start=min(starts))
            db.session.add(cohort)
            db.session.flush()
        cohorts_by_sheet[sheet_index] = cohort
    db.session.commit()
    log(f"cohorts: {len(cohorts_by_sheet)}")

    # ---- per-coder cascade, mirroring etl.py's `master` construction -----
    for full_name, rows in per_coder_rows.items():
        rows_by_month = {row["ramp_month"]: row for row in rows}
        prev_end = None
        cascade = []
        for i, stage in enumerate(STAGE_ORDER, start=1):
            row = rows_by_month.get(i)
            start = end = None
            if row is not None:
                start, end = row["actual_start"], row["actual_end"]
            if start is None and prev_end is not None:
                start = prev_end + dt.timedelta(days=1)
            if stage == "Steady State":
                end = None
            cascade.append({"stage_code": stage, "start_date": start, "end_date": end})
            prev_end = end if end is not None else (row["actual_end"] if row is not None else prev_end)

        m1_start = cascade[0]["start_date"]
        if m1_start is None:
            log(f"!! {full_name}: no M1 start could be determined from the workbook - skipped")
            continue

        cohort = cohorts_by_sheet.get(coder_sheet[full_name])
        coder = _get_or_create_coder(full_name, join_date=m1_start, cohort_id=cohort.id if cohort else None)
        coder.cohort_id = cohort.id if cohort else coder.cohort_id

        for alias in alias_map.get(full_name, ()):
            if not CoderAlias.query.filter_by(alias=alias).first():
                db.session.add(CoderAlias(coder_id=coder.id, alias=alias))

        # Training isn't represented for migrated coders - the old workbook
        # never tracked it, so there's nothing honest to backfill; their
        # timeline starts directly at M1 (see the plan's migration notes).
        CoderStagePeriod.query.filter_by(coder_id=coder.id).delete()
        for period in cascade:
            if period["start_date"] is None:
                continue
            db.session.add(
                CoderStagePeriod(
                    coder_id=coder.id,
                    stage_code=period["stage_code"],
                    start_date=period["start_date"],
                    end_date=period["end_date"],
                    source="manual_override",
                    shifted_by_exception_days=0,
                )
            )

        for d, count in old_grid_counts.get(full_name, {}).items():
            _upsert_manual_fact(coder.id, d, count)
    db.session.commit()
    log(f"ramp-tracked coders migrated: {len(per_coder_rows)}")

    # ---- 2. New-format manual production files ---------------------------
    manual_rows = 0
    for f in manual_files:
        df = read_manual(f)
        if df is None or df.empty:
            log(f"  no usable rows in {os.path.basename(f)}")
            continue
        for _, row in df.iterrows():
            coder = _get_or_create_coder(row["Coder"], join_date=row["Date"])
            _upsert_manual_fact(coder.id, row["Date"], row["Production count today"])
            manual_rows += 1
    db.session.commit()
    log(f"manual production rows ingested: {manual_rows}")

    # ---- 3. Kairon dumps -> deduplicated completions ----------------------
    seen_keys = set()
    kairon_rows = 0
    for f in kairon_files:
        df = read_kairon(f)
        if df is None or df.empty:
            log(f"  no usable rows in {os.path.basename(f)}")
            continue
        for _, row in df[df["Status"] == "Completed"].iterrows():
            completed = row["Completed"]
            if completed is None or pd.isna(completed):
                continue
            key = (row["MBI"], row["Level"], row["Coder"], completed)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            coder = _get_or_create_coder(row["Coder"], join_date=completed)
            exists = KaironCompletion.query.filter_by(
                mbi=row["MBI"], level=row["Level"], coder_id=coder.id, completed_date=completed
            ).first()
            if exists is None:
                db.session.add(
                    KaironCompletion(coder_id=coder.id, mbi=row["MBI"], level=row["Level"], completed_date=completed)
                )
                kairon_rows += 1
    db.session.commit()
    log(f"kairon completions ingested: {kairon_rows}")

    # ---- 4. No-ramp-history ("extra") coders -> Steady State only --------
    ramp_coder_names = set(per_coder_rows.keys())
    extra_count = 0
    for coder in Coder.query.filter(Coder.cohort_id.is_(None)).all():
        if coder.full_name in ramp_coder_names:
            continue  # ramp cascade failed above (already logged) - not an "extra" coder
        activity = first_activity_date(coder)
        if activity is None:
            continue
        coder.join_date = activity
        CoderStagePeriod.query.filter_by(coder_id=coder.id).delete()
        db.session.add(
            CoderStagePeriod(
                coder_id=coder.id,
                stage_code="Steady State",
                start_date=activity,
                end_date=None,
                source="manual_override",
                shifted_by_exception_days=0,
            )
        )
        extra_count += 1
    db.session.commit()
    log(f"no-ramp-history (tenured/BAU) coders: {extra_count}")

    # ---- 5. M1-start correction diff, for human sign-off ------------------
    log("\n--- M1 start correction diff (workbook ActualStart vs corrected first_activity_date) ---")
    diff_count = 0
    for full_name, rows in per_coder_rows.items():
        coder = Coder.query.filter_by(full_name=full_name).first()
        if coder is None:
            continue
        recorded_m1 = next((r["actual_start"] for r in rows if r["ramp_month"] == 1), None)
        if recorded_m1 is None:
            continue
        corrected = first_activity_date(coder)
        if corrected is None or corrected == recorded_m1:
            continue
        delta = (corrected - recorded_m1).days
        if abs(delta) > 3:
            diff_count += 1
            log(f"  {full_name}: workbook M1 start {recorded_m1} vs corrected {corrected} ({delta:+d}d)")
    log(f"--- {diff_count} coder(s) differ by more than 3 days - review before sign-off ---\n")
