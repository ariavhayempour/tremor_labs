from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.fakes import DATA_T0, FakeAnalysis, FakeClock, QuietSource, sim_batches
from tremorlab.config import Config
from tremorlab.db import queries as q
from tremorlab.db.connection import connect
from tremorlab.main import create_app
from tremorlab.sources.base import ImuBatch, TofBatch

EARLIER = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)


class Harness:
    def __init__(self, client: TestClient, clock: FakeClock) -> None:
        self.client = client
        self.clock = clock

    def feed(self, batches: list[ImuBatch | TofBatch]) -> None:
        broadcaster = self.client.app.state.broadcaster  # type: ignore[attr-defined]
        assert self.client.portal is not None
        for b in batches:
            self.client.portal.call(broadcaster.dispatch, b)
            self.clock.now = max(self.clock.now, float(b.t[-1]))

    def check(self) -> int:
        r = self.client.post("/api/checks", json={"medication": "not_yet"})
        assert r.status_code == 201
        return int(r.json()["check_id"])

    def start(self, check_id: int, kind: str = "rest") -> Any:
        return self.client.post(
            f"/api/checks/{check_id}/tests", json={"type": kind, "hand": "right"}
        )


def make_harness(config: Config, analysis: FakeAnalysis) -> Iterator[Harness]:
    clock = FakeClock()
    app = create_app(config, source=QuietSource(), analyzers=analysis.bundle(), clock=clock)
    with TestClient(app) as client:
        yield Harness(client, clock)


@pytest.fixture
def h(config: Config) -> Iterator[Harness]:
    yield from make_harness(config, FakeAnalysis())


def test_post_check_then_rest_flow_via_http(h: Harness) -> None:
    r = h.client.post(
        "/api/checks",
        json={"medication": "hours_ago", "hours_ago": 2, "caffeine": True, "sleep_quality": 4},
    )
    assert r.status_code == 201
    assert r.json() == {"check_id": r.json()["check_id"], "minutes_since_dose": 120.0}
    check_id = r.json()["check_id"]

    r = h.start(check_id)
    assert r.status_code == 201
    test_id = r.json()["test_id"]
    assert set(r.json()) == {"test_id"}

    h.feed(sim_batches(32))
    r = h.client.post(f"/api/tests/{test_id}/stop")
    assert r.status_code == 200
    body = r.json()
    assert body["test_id"] == test_id and body["status"] == "done"
    assert body["fail_reason"] is None
    assert body["result"]["peak_hz"] == 5.0 and body["result"]["smoothness"] is None
    assert max(body["result"]["details"]["freqs"]) == 15.0

    conn = h.client.app.state.conn  # type: ignore[attr-defined]
    check = q.get_check(conn, check_id)
    assert check is not None and check.caffeine is True and check.sleep_quality == 4
    assert check.created_at.timestamp() == pytest.approx(DATA_T0)
    assert len(q.raw_for_test(conn, test_id)) == 640


def test_second_start_via_http_returns_409(h: Harness) -> None:
    check_id = h.check()
    assert h.start(check_id).status_code == 201
    r = h.start(check_id, "posture")
    assert r.status_code == 409 and r.json()["error"] == "test_active"
    assert isinstance(r.json()["message"], str)


def test_start_on_unknown_check_is_404(h: Harness) -> None:
    r = h.start(999)
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_short_rest_via_http_is_200_failed(h: Harness) -> None:
    test_id = h.start(h.check()).json()["test_id"]
    h.feed(sim_batches(3))
    r = h.client.post(f"/api/tests/{test_id}/stop")
    assert r.status_code == 200
    assert r.json() == {
        "test_id": test_id,
        "status": "failed",
        "fail_reason": "insufficient_valid_data",
        "result": None,
    }


def test_stop_twice_is_invalid_state(h: Harness) -> None:
    test_id = h.start(h.check()).json()["test_id"]
    h.feed(sim_batches(10))
    assert h.client.post(f"/api/tests/{test_id}/stop").status_code == 200
    r = h.client.post(f"/api/tests/{test_id}/stop")
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"


def test_stop_and_mark_unknown_test_are_404(h: Harness) -> None:
    for action in ("stop", "mark"):
        r = h.client.post(f"/api/tests/999/{action}")
        assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_mark_returns_204(h: Harness) -> None:
    test_id = h.start(h.check(), "reach").json()["test_id"]
    r = h.client.post(f"/api/tests/{test_id}/mark")
    assert r.status_code == 204 and r.content == b""


def test_tap_start_returns_201(h: Harness) -> None:
    r = h.start(h.check(), "tap")
    assert r.status_code == 201
    r2 = h.client.post(f"/api/tests/{r.json()['test_id']}/stop")
    assert r2.status_code == 409 and r2.json()["error"] == "invalid_state"


def test_unimplemented_analysis_returns_501(config: Config) -> None:
    for harness in make_harness(config, FakeAnalysis(unimplemented=True)):
        test_id = harness.start(harness.check()).json()["test_id"]
        harness.feed(sim_batches(10))
        r = harness.client.post(f"/api/tests/{test_id}/stop")
        assert r.status_code == 501 and r.json()["error"] == "not_implemented"
        assert harness.start(harness.check()).status_code == 201


def test_startup_marks_leftover_recordings_interrupted(config: Config) -> None:
    conn = connect(config.db_path)
    check_id = q.insert_check(
        conn,
        created_at=EARLIER,
        minutes_since_dose=None,
        caffeine=None,
        sleep_quality=None,
        stress=None,
        alcohol=None,
        notes=None,
        dose_id=None,
    )
    tid = q.insert_test(conn, check_id=check_id, type="rest", hand="right", started_at=EARLIER)
    conn.close()
    for harness in make_harness(config, FakeAnalysis()):
        row = q.get_test(harness.client.app.state.conn, tid)  # type: ignore[attr-defined]
        assert row is not None and (row.status, row.fail_reason) == ("failed", "interrupted")


def test_default_app_lifespan_runs_session(client: TestClient) -> None:
    check = client.post("/api/checks", json={"medication": "now"})
    assert check.status_code == 201
    r = client.post(
        f"/api/checks/{check.json()['check_id']}/tests", json={"type": "rest", "hand": "left"}
    )
    assert r.status_code == 201
    with client.websocket_connect("/ws") as ws:
        for _ in range(60):
            m = ws.receive_json()
            if m["type"] == "status":
                break
    assert m["type"] == "status" and m["recording"] is True
    assert m["test_id"] == r.json()["test_id"] and m["test_type"] == "rest"
