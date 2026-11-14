import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.api.fakes import DATA_T0, FakeAnalysis, FakeClock, QuietSource
from tremorlab.config import Config
from tremorlab.db import queries as q
from tremorlab.doses import resolve_dose
from tremorlab.main import create_app

NOW = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)


def test_now_inserts_dose_minutes_zero(mem_conn: sqlite3.Connection) -> None:
    dose_id, minutes = resolve_dose(mem_conn, NOW, "now", None)
    assert dose_id is not None and minutes == 0.0
    [dose] = q.list_doses(mem_conn, None, None)
    assert dose.id == dose_id and dose.taken_at == NOW


def test_hours_ago_2_gives_120_minutes(mem_conn: sqlite3.Connection) -> None:
    dose_id, minutes = resolve_dose(mem_conn, NOW, "hours_ago", 2)
    assert minutes == pytest.approx(120.0)
    [dose] = q.list_doses(mem_conn, None, None)
    assert dose.id == dose_id and dose.taken_at == NOW - timedelta(hours=2)


def test_duplicate_within_30_min_reuses_dose(mem_conn: sqlite3.Connection) -> None:
    first, _ = resolve_dose(mem_conn, NOW - timedelta(minutes=20), "now", None)
    again, minutes = resolve_dose(mem_conn, NOW, "now", None)
    assert again == first and minutes == pytest.approx(20.0)
    assert len(q.list_doses(mem_conn, None, None)) == 1
    other, _ = resolve_dose(mem_conn, NOW, "hours_ago", 1)
    assert other != first and len(q.list_doses(mem_conn, None, None)) == 2


def test_reused_future_dose_never_gives_negative_minutes(mem_conn: sqlite3.Connection) -> None:
    q.insert_dose(mem_conn, NOW + timedelta(minutes=10))
    _, minutes = resolve_dose(mem_conn, NOW, "now", None)
    assert minutes == 0.0


def test_not_yet_uses_last_dose(mem_conn: sqlite3.Connection) -> None:
    old = q.insert_dose(mem_conn, NOW - timedelta(hours=5))
    last = q.insert_dose(mem_conn, NOW - timedelta(hours=3))
    q.insert_dose(mem_conn, NOW + timedelta(hours=1))
    dose_id, minutes = resolve_dose(mem_conn, NOW, "not_yet", None)
    assert dose_id == last != old and minutes == pytest.approx(180.0)
    assert len(q.list_doses(mem_conn, None, None)) == 3


def test_not_yet_without_any_dose_is_null(mem_conn: sqlite3.Connection) -> None:
    assert resolve_dose(mem_conn, NOW, "not_yet", None) == (None, None)
    assert q.list_doses(mem_conn, None, None) == []


def test_hours_ago_without_hours_is_rejected(mem_conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="hours_ago"):
        resolve_dose(mem_conn, NOW, "hours_ago", None)


@pytest.fixture
def client(config: Config) -> Iterator[TestClient]:
    app = create_app(
        config, source=QuietSource(), analyzers=FakeAnalysis().bundle(), clock=FakeClock()
    )
    with TestClient(app) as c:
        yield c


def test_post_check_returns_minutes_since_dose(client: TestClient) -> None:
    r = client.post("/api/checks", json={"medication": "hours_ago", "hours_ago": 2})
    assert r.status_code == 201 and r.json()["minutes_since_dose"] == pytest.approx(120.0)
    conn = client.app.state.conn  # type: ignore[attr-defined]
    check = q.get_check(conn, r.json()["check_id"])
    [dose] = q.list_doses(conn, None, None)
    assert check is not None and check.dose_id == dose.id
    assert check.minutes_since_dose == pytest.approx(120.0)
    assert dose.taken_at.timestamp() == pytest.approx(DATA_T0 - 7200)

    r = client.post("/api/checks", json={"medication": "not_yet"})
    assert r.json()["minutes_since_dose"] == pytest.approx(120.0)
    assert len(q.list_doses(conn, None, None)) == 1


def test_post_check_not_yet_without_dose_is_null(client: TestClient) -> None:
    r = client.post("/api/checks", json={"medication": "not_yet"})
    assert r.status_code == 201 and r.json()["minutes_since_dose"] is None
    check = q.get_check(client.app.state.conn, r.json()["check_id"])  # type: ignore[attr-defined]
    assert check is not None and check.dose_id is None and check.minutes_since_dose is None


def test_post_check_hours_ago_without_hours_is_422(client: TestClient) -> None:
    r = client.post("/api/checks", json={"medication": "hours_ago"})
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
    assert "hours_ago" in r.json()["message"]


def test_get_doses_filters_and_is_oldest_first(client: TestClient) -> None:
    conn = client.app.state.conn  # type: ignore[attr-defined]
    base = datetime.fromtimestamp(DATA_T0, UTC)
    late = q.insert_dose(conn, base - timedelta(hours=1), "evening")
    early = q.insert_dose(conn, base - timedelta(hours=10))
    r = client.get("/api/doses")
    assert r.status_code == 200
    assert [d["id"] for d in r.json()] == [early, late]
    assert r.json()[1]["label"] == "evening" and r.json()[0]["label"] is None
    assert datetime.fromisoformat(r.json()[0]["taken_at"]) == base - timedelta(hours=10)
    since = (base - timedelta(hours=2)).isoformat()
    r = client.get("/api/doses", params={"from": since})
    assert [d["id"] for d in r.json()] == [late]
    r = client.get("/api/doses", params={"to": since})
    assert [d["id"] for d in r.json()] == [early]
