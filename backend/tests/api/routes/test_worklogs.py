import decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import (
    Task,
    TimeSegment,
    TimeSegmentStatus,
    User,
    WorkLog,
)


def _seed_worklog_data(db: Session) -> None:
    """Seed Task, WorkLog, TimeSegment for superuser if none exist."""
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    if not user:
        return

    existing_wl = db.exec(select(WorkLog).where(WorkLog.user_id == user.id)).first()
    if existing_wl:
        return

    task1 = Task(title="Task Alpha", hourly_rate=decimal.Decimal("50.00"))
    task2 = Task(title="Task Beta", hourly_rate=decimal.Decimal("75.00"))
    db.add(task1)
    db.add(task2)
    db.flush()

    wl1 = WorkLog(user_id=user.id, task_id=task1.id)
    wl2 = WorkLog(user_id=user.id, task_id=task2.id)
    db.add(wl1)
    db.add(wl2)
    db.flush()

    db.add(TimeSegment(worklog_id=wl1.id, minutes=120, status=TimeSegmentStatus.ACTIVE))
    db.add(TimeSegment(worklog_id=wl1.id, minutes=60, status=TimeSegmentStatus.ACTIVE))
    db.add(TimeSegment(worklog_id=wl2.id, minutes=90, status=TimeSegmentStatus.ACTIVE))
    db.commit()


def test_generate_remittances_requires_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    """Without superuser auth, endpoint returns 403."""
    r = client.post(
        f"{settings.API_V1_STR}/generate-remittances-for-all-users",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403


def test_generate_remittances_for_all_users(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Superuser can generate remittances. Returns success message."""
    _seed_worklog_data(db)

    r = client.post(
        f"{settings.API_V1_STR}/generate-remittances-for-all-users",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "message" in data
    assert "remittance" in data["message"].lower() or "Generated" in data["message"]


def test_list_all_worklogs_requires_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    """Without superuser auth, list endpoint returns 403."""
    r = client.get(
        f"{settings.API_V1_STR}/list-all-worklogs",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403


def test_list_all_worklogs_no_filter(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """List worklogs without filter returns data with amount per worklog."""
    _seed_worklog_data(db)

    r = client.get(
        f"{settings.API_V1_STR}/list-all-worklogs",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert "count" in data
    assert isinstance(data["data"], list)
    for wl in data["data"]:
        assert "amount" in wl
        assert "id" in wl
        assert "remittance_status" in wl
        assert wl["remittance_status"] in ("REMITTED", "UNREMITTED")


def test_list_all_worklogs_filter_remitted(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Filter remittanceStatus=REMITTED returns only remitted worklogs."""
    _seed_worklog_data(db)
    client.post(
        f"{settings.API_V1_STR}/generate-remittances-for-all-users",
        headers=superuser_token_headers,
    )

    r = client.get(
        f"{settings.API_V1_STR}/list-all-worklogs",
        params={"remittanceStatus": "REMITTED"},
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    for wl in data["data"]:
        assert wl["remittance_status"] == "REMITTED"
        assert "amount" in wl


def test_list_all_worklogs_filter_unremitted(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Filter remittanceStatus=UNREMITTED returns only unremitted worklogs."""
    _seed_worklog_data(db)

    r = client.get(
        f"{settings.API_V1_STR}/list-all-worklogs",
        params={"remittanceStatus": "UNREMITTED"},
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    for wl in data["data"]:
        assert wl["remittance_status"] == "UNREMITTED"


def test_list_all_worklogs_invalid_filter_returns_empty(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Invalid remittanceStatus returns empty data."""
    r = client.get(
        f"{settings.API_V1_STR}/list-all-worklogs",
        params={"remittanceStatus": "INVALID"},
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["data"] == []
    assert data["count"] == 0


def test_list_all_worklogs_pagination(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Pagination skip/limit works."""
    _seed_worklog_data(db)

    r = client.get(
        f"{settings.API_V1_STR}/list-all-worklogs",
        params={"skip": 0, "limit": 1},
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["data"]) <= 1
    assert data["count"] >= 0


def test_generate_remittances_idempotent_second_run(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Second generate run creates remittances for newly eligible work only."""
    _seed_worklog_data(db)

    r1 = client.post(
        f"{settings.API_V1_STR}/generate-remittances-for-all-users",
        headers=superuser_token_headers,
    )
    assert r1.status_code == 200

    r2 = client.post(
        f"{settings.API_V1_STR}/generate-remittances-for-all-users",
        headers=superuser_token_headers,
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert "Generated 0 remittance" in data2["message"]
