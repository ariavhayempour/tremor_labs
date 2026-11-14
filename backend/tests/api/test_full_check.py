from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.fakes import FakeAnalysis, FakeClock, QuietSource, sim_batches
from tests.api.test_tests_api import Harness, make_harness
from tests.test_session_reach_tap import descent_segments, frames
from tremorlab.analysis import baseline
from tremorlab.config import Config
from tremorlab.db import queries as q
from tremorlab.main import create_app

HOUR_S = 3600.0
LM = [[0.5, 0.8], [0.4, 0.4], [0.45, 0.4], [0.5, 0.5]]


@pytest.fixture
def h(config: Config) -> Iterator[Harness]:
    yield from make_harness(config, FakeAnalysis(tap_rates=(3.0, 5.0)))


def start(h: Harness, check_id: int, kind: str, hand: str = "right") -> int:
    r = h.client.post(f"/api/checks/{check_id}/tests", json={"type": kind, "hand": hand})
    assert r.status_code == 201, r.text
    return int(r.json()["test_id"])


def tap_body(n: int = 40) -> dict[str, Any]:
    return {"frames": [{"t_ms": 1000.0 + 33.3 * i, "lm": LM} for i in range(n)]}


def run_rest(h: Harness, check_id: int) -> int:
    tid = start(h, check_id, "rest")
    h.feed(sim_batches(32, t0=h.clock.now))
    assert h.client.post(f"/api/tests/{tid}/stop").json()["status"] == "done"
    return tid


def run_tap(h: Harness, check_id: int, hand: str, n: int = 40) -> dict[str, Any]:
    tid = start(h, check_id, "tap", hand)
    r = h.client.post(f"/api/tests/{tid}/tap-data", json=tap_body(n))
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def summary(h: Harness, check_id: int) -> dict[str, Any]:
    r = h.client.get(f"/api/checks/{check_id}")
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def cards(h: Harness, check_id: int) -> dict[str, dict[str, Any]]:
    return {c["test"]: c for c in summary(h, check_id)["cards"]}


def test_tap_data_route_converts_ms_and_stores(config: Config) -> None:
    analysis = FakeAnalysis()
    for h in make_harness(config, analysis):
        tid = start(h, h.check(), "tap", "left")
        body = tap_body()
        body["frames"][1]["lm"] = None
        r = h.client.post(f"/api/tests/{tid}/tap-data", json=body)
        assert r.status_code == 200
        out = r.json()
        assert out["test_id"] == tid and out["status"] == "done" and out["fail_reason"] is None
        assert out["result"]["taps_per_sec"] == 4.0
        assert set(out["result"]["details"]) == {"t", "signal", "peaks"}
        [call] = analysis.tap_calls
        assert call[0].t == pytest.approx(1.0) and call[1].lm is None
        assert call[2].lm == tuple(tuple(p) for p in LM)
        assert q.get_result(h.client.app.state.conn, tid) is not None  # type: ignore[attr-defined]


def test_tap_data_without_taps_is_200_failed(h: Harness) -> None:
    tid = start(h, h.check(), "tap")
    body = {"frames": [{"t_ms": float(i), "lm": None} for i in range(10)]}
    r = h.client.post(f"/api/tests/{tid}/tap-data", json=body)
    assert r.status_code == 200
    assert r.json() == {
        "test_id": tid,
        "status": "failed",
        "fail_reason": "no_taps_detected",
        "result": None,
    }


def test_tap_data_on_non_tap_or_finished_test_is_409(h: Harness) -> None:
    check_id = h.check()
    rest = start(h, check_id, "rest")
    r = h.client.post(f"/api/tests/{rest}/tap-data", json=tap_body())
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"
    h.client.post(f"/api/tests/{rest}/stop")
    tap = start(h, check_id, "tap")
    assert h.client.post(f"/api/tests/{tap}/tap-data", json=tap_body()).status_code == 200
    r = h.client.post(f"/api/tests/{tap}/tap-data", json=tap_body())
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"


def test_tap_data_unknown_test_is_404_and_bad_landmarks_422(h: Harness) -> None:
    r = h.client.post("/api/tests/999/tap-data", json=tap_body())
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    tid = start(h, h.check(), "tap")
    bad = {"frames": [{"t_ms": 0.0, "lm": LM[:3]}]}
    r = h.client.post(f"/api/tests/{tid}/tap-data", json=bad)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"


def test_reach_stop_via_http_returns_attempt_curves(h: Harness) -> None:
    tid = start(h, h.check(), "reach")
    for i, seg in enumerate(descent_segments(3, 5.0, t0=h.clock.now)):
        if i:
            assert h.client.post(f"/api/tests/{tid}/mark").status_code == 204
        h.feed(seg)
    r = h.client.post(f"/api/tests/{tid}/stop")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done" and body["result"]["smoothness"] == 2.5
    assert len(body["result"]["details"]["attempts"]) == 3


def test_list_checks_newest_first_with_tests_in_start_order(h: Harness) -> None:
    first = h.check()
    run_rest(h, first)
    tap = run_tap(h, first, "left")
    h.clock.now += HOUR_S
    second = h.check()
    failed = start(h, second, "rest")
    h.feed(sim_batches(3, t0=h.clock.now))
    h.client.post(f"/api/tests/{failed}/stop")

    r = h.client.get("/api/checks")
    assert r.status_code == 200
    body = r.json()
    assert [c["id"] for c in body] == [second, first]
    assert [t["type"] for t in body[1]["tests"]] == ["rest", "tap"]
    assert body[1]["tests"][1]["id"] == tap["test_id"] and body[1]["tests"][1]["hand"] == "left"
    assert body[1]["tests"][0]["result"]["strength_score"] == 50.0
    [t] = body[0]["tests"]
    assert (t["status"], t["fail_reason"], t["result"]) == (
        "failed",
        "insufficient_valid_data",
        None,
    )
    assert set(body[0]) >= {"created_at", "minutes_since_dose", "dose_id", "notes"}

    cutoff = datetime.fromtimestamp(h.clock.now - HOUR_S / 2, UTC).isoformat()
    assert [c["id"] for c in h.client.get("/api/checks", params={"from": cutoff}).json()] == [
        second
    ]
    assert [c["id"] for c in h.client.get("/api/checks", params={"to": cutoff}).json()] == [first]


def test_summary_has_four_cards_in_order(h: Harness) -> None:
    check_id = h.check()
    run_rest(h, check_id)
    posture = start(h, check_id, "posture")
    h.feed(sim_batches(1, t0=h.clock.now))
    h.feed(sim_batches(1, t0=h.clock.now + 3.0))  # a link gap fails the test
    assert h.client.post(f"/api/tests/{posture}/stop").json()["status"] == "failed"
    body = summary(h, check_id)
    assert body["check"]["id"] == check_id and len(body["check"]["tests"]) == 2
    got = [(c["test"], c["metric"], c["unit"], c["status"]) for c in body["cards"]]
    assert got == [
        ("rest", "strength_score", "score", "done"),
        ("posture", "strength_score", "score", "failed"),
        ("reach", "smoothness", "mm", "missing"),
        ("tap", "taps_per_sec", "taps/s", "missing"),
    ]
    rest, posture_card, reach, _ = body["cards"]
    assert rest["value"] == 50.0 and posture_card["value"] is None and reach["value"] is None
    assert all(c["baseline_pct"] is None and c["baseline_n"] == 0 for c in body["cards"])


def test_tap_mean_over_both_hands_in_summary(h: Harness) -> None:
    check_id = h.check()
    run_tap(h, check_id, "left")
    run_tap(h, check_id, "right")
    tap = cards(h, check_id)["tap"]
    assert tap["status"] == "done" and tap["value"] == pytest.approx(4.0)

    one_hand = h.check()
    run_tap(h, one_hand, "left")
    run_tap(h, one_hand, "right", n=1)  # fails: no taps
    tap = cards(h, one_hand)["tap"]
    assert tap["status"] == "done" and tap["value"] == pytest.approx(3.0)  # rates cycle 3, 5

    none_done = h.check()
    run_tap(h, none_done, "left", n=1)
    tap = cards(h, none_done)["tap"]
    assert (tap["status"], tap["value"]) == ("failed", None)


def test_summary_baseline_null_below_three_without_compare(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(value: float, history: Sequence[float], min_n: int = 3) -> float | None:
        raise AssertionError("compare must not run below three entries")

    monkeypatch.setattr(baseline, "compare", boom)
    for _ in range(3):
        run_rest(h, h.check())
        h.clock.now += HOUR_S
    rest = cards(h, h.check())["rest"]
    assert rest["status"] == "missing" and rest["baseline_n"] == 3
    assert rest["baseline_pct"] is None
    third = h.client.get("/api/checks").json()[1]["id"]
    rest = cards(h, third)["rest"]
    assert rest["baseline_n"] == 2 and rest["baseline_pct"] is None


def test_summary_baseline_pct_uses_earlier_checks(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[float, list[float]]] = []

    def fake_compare(value: float, history: Sequence[float], min_n: int = 3) -> float | None:
        calls.append((value, list(history)))
        return 12.5

    monkeypatch.setattr(baseline, "compare", fake_compare)
    for _ in range(3):
        check_id = h.check()
        run_rest(h, check_id)
        run_tap(h, check_id, "left")
        run_tap(h, check_id, "right")
        h.clock.now += HOUR_S
    current = h.check()
    run_rest(h, current)
    run_tap(h, current, "left")
    run_tap(h, current, "right")
    later = h.check()  # a newer check never counts towards an older one's baseline
    run_rest(h, later)

    got = cards(h, current)
    assert got["rest"]["baseline_pct"] == 12.5 and got["rest"]["baseline_n"] == 3
    assert got["tap"]["baseline_pct"] == 12.5 and got["tap"]["baseline_n"] == 3
    assert got["reach"]["baseline_n"] == 0 and got["reach"]["baseline_pct"] is None
    assert sorted(calls) == sorted([(50.0, [50.0] * 3), (4.0, [4.0] * 3)])


def test_summary_unknown_check_is_404(h: Harness) -> None:
    r = h.client.get("/api/checks/999")
    assert r.status_code == 404 and r.json()["error"] == "not_found"


@pytest.mark.integration
def test_full_check_end_to_end(config: Config) -> None:
    clock = FakeClock()
    with TestClient(create_app(config, source=QuietSource(), clock=clock)) as client:
        h = Harness(client, clock)
        r = h.client.post("/api/checks", json={"medication": "now", "caffeine": False})
        check_id = r.json()["check_id"]
        ids = [run_rest(h, check_id)]
        posture = start(h, check_id, "posture")
        h.feed(sim_batches(32, t0=h.clock.now))
        assert h.client.post(f"/api/tests/{posture}/stop").json()["status"] == "done"
        reach = start(h, check_id, "reach")
        for i, seg in enumerate(descent_segments(3, 5.0, t0=h.clock.now)):
            if i:
                h.client.post(f"/api/tests/{reach}/mark")
            h.feed(seg)
        assert h.client.post(f"/api/tests/{reach}/stop").json()["status"] == "done"
        ids += [posture, reach]
        for hand in ("left", "right"):
            tid = start(h, check_id, "tap", hand)
            body = {"frames": [{"t_ms": f.t * 1000, "lm": f.lm} for f in frames(300)]}
            out = h.client.post(f"/api/tests/{tid}/tap-data", json=body).json()
            assert out["status"] == "done"
            ids.append(tid)
        body = summary(h, check_id)
        assert [c["test"] for c in body["cards"]] == ["rest", "posture", "reach", "tap"]
        assert all(c["status"] == "done" and c["value"] is not None for c in body["cards"])
        assert all(t["status"] == "done" for t in body["check"]["tests"])
        conn = h.client.app.state.conn  # type: ignore[attr-defined]
        assert all(q.get_result(conn, tid) is not None for tid in ids)
        assert all(q.raw_for_test(conn, tid) for tid in ids[:3])


def test_list_checks_details_false_omits_curves_keeps_metrics(h: Harness) -> None:
    check_id = h.check()
    run_rest(h, check_id)

    [full] = h.client.get("/api/checks").json()
    assert full["tests"][0]["result"]["details"]["freqs"]  # curves by default

    [lean] = h.client.get("/api/checks", params={"details": "false"}).json()
    result = lean["tests"][0]["result"]
    assert result["details"] == {}
    assert result["strength_score"] == full["tests"][0]["result"]["strength_score"]

    one = h.client.get(f"/api/checks/{check_id}").json()
    assert one["check"]["tests"][0]["result"]["details"]["freqs"]  # single check keeps curves


def test_list_checks_rejects_bad_details_flag(h: Harness) -> None:
    r = h.client.get("/api/checks", params={"details": "maybe"})
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
