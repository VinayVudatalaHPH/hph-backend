import datetime as dt

from app.encryption.passwords import hash_password
from app.extensions import db
from app.manual_daily_records.models import ManualDailyRecord
from app.manual_daily_records.services import upsert_own_record
from app.roles.models import Role, RoleType
from app.users.models import User


def _get_or_create_user(email, first_name, last_name, emp_id):
    role_type = RoleType.query.filter_by(code="employee").one()
    role = Role.query.filter_by(role_type_id=role_type.id).first()
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            emp_id=emp_id,
            role_id=role.id,
            password_hash=hash_password("test-password"),
            first_login=False,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
    return user


def _entry(**overrides):
    entry = {
        "record_date": dt.date(2026, 9, 10),
        "production_count": 12,
        "tech_issues_downtime_hours": 1,
        "no_inventory_idle_time_hours": 0.5,
        "leave_hours": 0,
        "meeting_engagement_hours": 1.5,
    }
    entry.update(overrides)
    return entry


def _entry_body(**overrides):
    body = {
        "date": "2026-09-10",
        "productionCount": 12,
        "techIssuesDowntimeHours": 1,
        "noInventoryIdleTimeHours": 0.5,
        "leaveHours": 0,
        "meetingEngagementHours": 1.5,
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------------------
# Service-level: the upsert itself, without the HTTP/crypto layer.
# --------------------------------------------------------------------------


def test_upsert_creates_new_record_as_pending():
    user = _get_or_create_user("mdr-owner1@example.com", "Owner", "One", "TEST-MDR-1")

    record = upsert_own_record(user.id, _entry())

    assert record.user_id == user.id
    assert record.record_date == dt.date(2026, 9, 10)
    assert record.production_count == 12
    assert record.status == "pending"


def test_upsert_updates_existing_record_instead_of_duplicating():
    user = _get_or_create_user("mdr-owner2@example.com", "Owner", "Two", "TEST-MDR-2")

    first = upsert_own_record(user.id, _entry(production_count=10))
    second = upsert_own_record(user.id, _entry(production_count=25))

    assert first.id == second.id
    assert ManualDailyRecord.query.filter_by(user_id=user.id, record_date=dt.date(2026, 9, 10)).count() == 1
    assert second.production_count == 25


def test_upsert_resets_status_to_pending_on_edit():
    user = _get_or_create_user("mdr-owner3@example.com", "Owner", "Three", "TEST-MDR-3")
    manager = _get_or_create_user("mdr-manager1@example.com", "Manager", "One", "TEST-MDR-MGR-1")

    record = upsert_own_record(user.id, _entry())
    record.status = "approved"
    record.reviewed_by_id = manager.id
    record.reviewed_at = dt.datetime.now(dt.timezone.utc)
    db.session.commit()

    edited = upsert_own_record(user.id, _entry(production_count=99))

    assert edited.status == "pending"
    assert edited.reviewed_by_id is None
    assert edited.reviewed_at is None
    assert edited.production_count == 99


# --------------------------------------------------------------------------
# API-level: self-entry, role gating on review, and the group filters -
# through the real encrypted request/response cycle (see conftest.ApiClient).
# --------------------------------------------------------------------------


def test_employee_can_self_enter_and_edit_own_record(api_client, employee_user):
    status, _ = api_client.login("test-employee@example.com", "test-password")
    assert status == 200

    status, body = api_client.post("/api/manual-daily-records", _entry_body())
    assert status == 200, body
    assert body["data"]["userId"] == employee_user.id
    assert body["data"]["status"] == "pending"
    assert body["data"]["productionCount"] == 12

    status, body = api_client.post("/api/manual-daily-records", _entry_body(productionCount=30))
    assert status == 200, body
    assert body["data"]["productionCount"] == 30

    status, body = api_client.get(f"/api/manual-daily-records?userId={employee_user.id}")
    assert status == 200, body
    assert len(body["data"]) == 1
    assert body["data"][0]["productionCount"] == 30


def test_program_counts_are_added_into_production_total(api_client, employee_user):
    api_client.login("test-employee@example.com", "test-password")

    status, body = api_client.post(
        "/api/manual-daily-records",
        _entry_body(productionCount=None, pvpCount=11, foundationCount=7),
    )

    assert status == 200, body
    assert body["data"]["pvpCount"] == 11
    assert body["data"]["foundationCount"] == 7
    assert body["data"]["productionCount"] == 18


def test_production_count_cannot_be_negative(api_client, employee_user):
    api_client.login("test-employee@example.com", "test-password")

    status, body = api_client.post("/api/manual-daily-records", _entry_body(productionCount=-1))
    assert status == 422, body


def test_hour_field_cannot_exceed_ten(api_client, employee_user):
    api_client.login("test-employee@example.com", "test-password")

    status, body = api_client.post("/api/manual-daily-records", _entry_body(techIssuesDowntimeHours=40))
    assert status == 422, body


def test_non_manager_cannot_approve_or_reject(api_client, employee_user):
    api_client.login("test-employee@example.com", "test-password")
    status, body = api_client.post("/api/manual-daily-records", _entry_body())
    record_id = body["data"]["id"]

    status, body = api_client.post(f"/api/manual-daily-records/{record_id}/approve")
    assert status == 403, body


def test_manager_can_approve_pending_record(api_client, employee_user, manager_user):
    api_client.login("test-employee@example.com", "test-password")
    status, body = api_client.post("/api/manual-daily-records", _entry_body())
    record_id = body["data"]["id"]

    api_client.login("test-manager@example.com", "test-password")
    status, body = api_client.post(f"/api/manual-daily-records/{record_id}/approve")
    assert status == 200, body
    assert body["data"]["status"] == "approved"
    assert body["data"]["reviewedById"] == manager_user.id

    # Already reviewed - a second decision is rejected outright.
    status, body = api_client.post(f"/api/manual-daily-records/{record_id}/reject", {"reason": "too late"})
    assert status == 409, body


def test_manager_can_reject_pending_record_with_reason(api_client, employee_user, manager_user):
    api_client.login("test-employee@example.com", "test-password")
    status, body = api_client.post("/api/manual-daily-records", _entry_body())
    record_id = body["data"]["id"]

    api_client.login("test-manager@example.com", "test-password")
    status, body = api_client.post(
        f"/api/manual-daily-records/{record_id}/reject", {"reason": "hours look wrong"}
    )
    assert status == 200, body
    assert body["data"]["status"] == "rejected"
    assert body["data"]["rejectionReason"] == "hours look wrong"


def test_query_filters_by_user_ids_and_excludes(api_client, manager_user):
    user_a = _get_or_create_user("mdr-a@example.com", "Alpha", "User", "TEST-MDR-A")
    user_b = _get_or_create_user("mdr-b@example.com", "Beta", "User", "TEST-MDR-B")
    upsert_own_record(user_a.id, _entry(record_date=dt.date(2026, 9, 11)))
    upsert_own_record(user_b.id, _entry(record_date=dt.date(2026, 9, 11)))

    api_client.login("test-manager@example.com", "test-password")

    status, body = api_client.get(f"/api/manual-daily-records?userIds={user_a.id}&userIds={user_b.id}")
    assert status == 200, body
    assert {row["userId"] for row in body["data"]} == {user_a.id, user_b.id}

    status, body = api_client.get(
        f"/api/manual-daily-records?fromDate=2026-09-11&toDate=2026-09-11&excludeUserIds={user_b.id}"
    )
    assert status == 200, body
    assert {row["userId"] for row in body["data"]} == {user_a.id}
