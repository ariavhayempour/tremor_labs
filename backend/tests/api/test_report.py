from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.fakes import FakeClock, QuietSource
from tests.api.test_insights_api import NOW, TODAY, TZ, add_check, conn_of, rest
from tremorlab.config import Config
from tremorlab.db.models import ResultRow
from tremorlab.main import create_app

REPORT_KEYS = {
    "period",
    "checks_completed",
    "dose_response",
    "returns_after_h",
    "profile",
    "daily",
    "generated_at",
}


@pytest.fixture
def client(config: Config) -> Iterator[TestClient]:
    app = create_app(config, source=QuietSource(), clock=FakeClock(NOW.timestamp()))
    app.state.tz = TZ
    with TestClient(app) as c:
        yield c


@pytest.fixture
def filled(client: TestClient) -> TestClient:
    """Checks on several days covering every test type, at various times since dose."""
    conn = conn_of(client)
    for day, minutes, strength in [(10, 30.0, 0.1), (5, 200.0, 0.4), (1, 60.0, 0.15)]:
        add_check(
            conn,
            NOW - timedelta(days=day),
            [
                ("rest", "right", "done", rest(strength)),
                ("posture", "right", "done", rest(strength / 2)),
                ("reach", "right", "done", ResultRow(smoothness=3.0, wobble_ratio=0.1)),
                ("tap", "right", "done", ResultRow(taps_per_sec=4.0)),
            ],
            minutes=minutes,
        )
    return client


def get(client: TestClient, path: str, **params: Any) -> Any:
    r = client.get(path, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_report_includes_counts_for_every_insight(filled: TestClient) -> None:
    body = get(filled, "/api/report")
    assert set(body) == REPORT_KEYS
    assert body["dose_response"] and all(b["count"] > 0 for b in body["dose_response"])
    assert [p["test_type"] for p in body["profile"]] == ["rest", "posture", "reach", "tap"]
    assert all(
        isinstance(p["first_n"], int) and isinstance(p["current_n"], int) for p in body["profile"]
    )
    assert len(body["daily"]) == 14 and all(isinstance(d["count"], int) for d in body["daily"])
    assert sum(d["count"] for d in body["daily"]) == 3
    assert body["checks_completed"] == 3


def test_report_matches_the_insight_endpoints(filled: TestClient) -> None:
    body = get(filled, "/api/report", days=7)
    dose = get(filled, "/api/insights/dose-response", days=7)
    summary = get(filled, "/api/insights/summary", days=7)
    assert body["dose_response"] == dose["bins"]
    assert body["returns_after_h"] == dose["returns_after_h"]
    assert body["profile"] == get(filled, "/api/insights/profile", days=7)
    assert body["daily"] == summary["daily"]
    assert body["checks_completed"] == summary["checks_completed"] == 2


def test_report_period_is_the_local_day_window(client: TestClient) -> None:
    body = get(client, "/api/report", days=3)
    start = datetime.combine(TODAY - timedelta(days=2), time(), tzinfo=TZ).astimezone(UTC)
    assert datetime.fromisoformat(body["period"]["start"]) == start
    assert datetime.fromisoformat(body["period"]["end"]) == NOW
    assert datetime.fromisoformat(body["generated_at"]) == NOW


def test_empty_report_has_zero_counts(client: TestClient) -> None:
    body = get(client, "/api/report")
    assert body["checks_completed"] == 0 and body["dose_response"] == []
    assert body["returns_after_h"] is None
    assert all(p["first_n"] == 0 and p["current_n"] == 0 for p in body["profile"])
    assert all(d["count"] == 0 and d["mean_rest"] is None for d in body["daily"])


@pytest.mark.parametrize("days", [0, 366])
def test_report_days_out_of_range_is_422(client: TestClient, days: int) -> None:
    r = client.get("/api/report", params={"days": days})
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
