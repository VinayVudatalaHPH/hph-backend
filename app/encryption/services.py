from datetime import datetime, timedelta, timezone

from app.encryption.crypto import generate_key, unwrap_key, wrap_key
from app.encryption.models import GRACE_PERIOD_HOURS, KEY_LIFETIME_DAYS, EncryptionKey
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


def get_active_key_record():
    return EncryptionKey.query.filter_by(is_active=True).one_or_none()


def get_active_key():
    """Returns (key_version, raw_key_bytes) for the currently active key."""
    record = get_active_key_record()
    if record is None:
        raise RuntimeError("No active EncryptionKey — has the seed migration run?")
    return record.key_version, unwrap_key(record.wrapped_key)


def get_key_for_decryption(key_version):
    """Raw key bytes for `key_version` if still valid for decryption — either
    the active key, or a rotated-out key still inside its grace window (so a
    request already in flight at rotation time, or a client that hasn't
    noticed the rotation yet, still decrypts correctly). None if unknown or
    past its grace window.
    """
    record = db.session.get(EncryptionKey, key_version)
    if record is None:
        return None

    if record.is_active:
        return unwrap_key(record.wrapped_key)

    if _now() <= record.expires_at + timedelta(hours=GRACE_PERIOD_HOURS):
        return unwrap_key(record.wrapped_key)

    return None


def rotate_key(force=False):
    """Activates a freshly generated key, deactivating (not deleting) the
    previous one. `force=True` bypasses the 20-day-expiry check, for manual/
    out-of-cycle rotation (flask rotate-encryption-key) or a scheduled Beat
    task that's already confirmed the active key is due. Returns the new
    EncryptionKey record, or the still-current one if rotation isn't due and
    `force` wasn't set.
    """
    active = get_active_key_record()
    if active is not None and not force and _now() < active.expires_at:
        return active

    now = _now()
    if active is not None:
        # flushed separately so the two rows are never both `is_active=true`
        # at once, which the partial unique index would reject.
        active.is_active = False
        db.session.add(active)
        db.session.flush()

    new_key = EncryptionKey(
        wrapped_key=wrap_key(generate_key()),
        activated_at=now,
        expires_at=now + timedelta(days=KEY_LIFETIME_DAYS),
        is_active=True,
    )
    db.session.add(new_key)
    db.session.commit()
    return new_key
