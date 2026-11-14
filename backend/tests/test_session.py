from collections.abc import Iterator
from typing import Any

import pytest

from tests.api.fakes import DATA_T0, FakeAnalysis, FakeClock, sim_batches
from tremorlab.config import SimParams
from tremorlab.db import queries as q
from tremorlab.db.connection import connect
from tremorlab.session import (
    MAX_RECORDING_S,
    ActiveTestError,
    AnalysisUnavailableError,
    InvalidStateError,
    NotFoundError,
    TestSession,
    default_analyzers,
)
from tremorlab.sources.base import ImuBatch, TofBatch
from tremorlab.sources.simulated import SimulatedSource
from tremorlab.stream.broadcaster import Broadcaster


class Rig:
    def __init__(self, analysis: FakeAnalysis | None = None, *, real: bool = False) -> None:
        self.conn = connect(":memory:")
        self.broadcaster = Broadcaster(SimulatedSource(SimParams(), fast=True, seed=0))
        self.clock = FakeClock()
        self.analysis = analysis or FakeAnalysis()
        self.session = TestSession(
            self.conn,
            self.broadcaster,
            self.broadcaster.source,
            analyzers=default_analyzers() if real else self.analysis.bundle(),
            clock=self.clock,
        )
        self.queue = self.broadcaster.subscribe()
        self.check_id = q.insert_check(
            self.conn,
            created_at=self.session.now(),
            minutes_since_dose=None,
            caffeine=None,
            sleep_quality=None,
            stress=None,
            alcohol=None,
            notes=None,
            dose_id=None,
        )

    def feed(self, batches: list[ImuBatch | TofBatch]) -> None:
        for b in batches:
            self.broadcaster.dispatch(b)
            self.clock.now = max(self.clock.now, float(b.t[-1]))

    def messages(self, kind: str) -> list[dict[str, Any]]:
        out = []
        while not self.queue.empty():
            m = self.queue.get_nowait()
            if m["type"] == kind:
                out.append(m)
        return out


@pytest.fixture
def rig() -> Iterator[Rig]:
    r = Rig()
    yield r
    r.conn.close()


def test_rest_test_stores_done_result(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "rest", "right")
    rig.feed(sim_batches(32))
    out = rig.session.stop(tid)
    assert out.status == "done" and out.fail_reason is None and out.result is not None
    assert out.result.peak_hz == 5.0 and out.result.strength_score == 50.0
    assert out.result.valid_seconds == pytest.approx(31.99, abs=0.02)
    freqs = out.result.details["freqs"]
    assert max(freqs) == 15.0 and len(freqs) == len(out.result.details["psd"]) == 61
    assert out.result.details["psd"][0] == 0.01235
    stored = q.get_result(rig.conn, tid)
    assert stored is not None and stored.peak_hz == 5.0 and stored.details["freqs"] == freqs
    [row] = q.tests_for_check(rig.conn, rig.check_id)
    assert row.status == "done" and row.ended_at is not None
    assert rig.analysis.tremor_calls[-1]["trim"] is True
    assert rig.session.active is None


@pytest.mark.integration
def test_rest_test_records_and_detects_5hz() -> None:
    rig = Rig(real=True)
    tid = rig.session.start(rig.check_id, "rest", "right")
    rig.feed(sim_batches(32))
    out = rig.session.stop(tid)
    assert out.status == "done" and out.result is not None and out.result.peak_hz is not None
    assert abs(out.result.peak_hz - 5.0) <= 0.25


def test_second_start_while_recording_returns_409(rig: Rig) -> None:
    rig.session.start(rig.check_id, "rest", "right")
    rig.clock.now += 119.0
    with pytest.raises(ActiveTestError):
        rig.session.start(rig.check_id, "posture", "right")
    with pytest.raises(ActiveTestError):
        rig.session.start(rig.check_id, "tap", "left")


def test_stale_recording_is_interrupted(rig: Rig) -> None:
    old = rig.session.start(rig.check_id, "rest", "right")
    rig.feed(sim_batches(2))
    rig.clock.now += 121.0
    new = rig.session.start(rig.check_id, "rest", "right")
    rows = {t.id: t for t in q.tests_for_check(rig.conn, rig.check_id)}
    assert (rows[old].status, rows[old].fail_reason) == ("failed", "interrupted")
    assert rows[new].status == "recording"
    assert rig.session.active is not None and rig.session.active.test_id == new
    with pytest.raises(InvalidStateError):
        rig.session.stop(old)


def test_orphaned_tap_row_older_than_120s_is_interrupted(rig: Rig) -> None:
    tap = rig.session.start(rig.check_id, "tap", "left")
    rig.clock.now += 121.0
    rig.session.start(rig.check_id, "rest", "right")
    row = q.get_test(rig.conn, tap)
    assert row is not None and (row.status, row.fail_reason) == ("failed", "interrupted")


def test_gap_in_recording_fails_with_sensor_disconnected(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "rest", "right")
    batches = sim_batches(32)
    rig.feed([b for b in batches if not 10.0 <= b.t[0] - DATA_T0 < 12.0])
    out = rig.session.stop(tid)
    assert (out.status, out.fail_reason, out.result) == ("failed", "sensor_disconnected", None)
    row = q.get_test(rig.conn, tid)
    assert row is not None and (row.status, row.fail_reason) == ("failed", "sensor_disconnected")
    assert q.get_result(rig.conn, tid) is None
    assert rig.analysis.tremor_calls == []


def test_no_data_at_all_fails_with_sensor_disconnected(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "rest", "right")
    rig.clock.now += 30.0
    out = rig.session.stop(tid)
    assert (out.status, out.fail_reason) == ("failed", "sensor_disconnected")


def test_short_rest_fails_insufficient(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "rest", "right")
    rig.feed(sim_batches(5))
    out = rig.session.stop(tid)
    assert (out.status, out.fail_reason, out.result) == ("failed", "insufficient_valid_data", None)
    row = q.get_test(rig.conn, tid)
    assert row is not None and row.fail_reason == "insufficient_valid_data"


def test_posture_uses_band_from_start_height(rig: Rig) -> None:
    rig.feed(sim_batches(2, SimParams(hand_mm=250.0)))
    tid = rig.session.start(rig.check_id, "posture", "right")
    active = rig.session.active
    assert active is not None and active.band is not None
    assert active.band == pytest.approx((220.0, 280.0), abs=5.0)
    rig.feed(sim_batches(25, SimParams(hand_mm=250.0), t0=DATA_T0 + 2.0))
    out = rig.session.stop(tid)
    assert out.status == "done"
    assert rig.analysis.posture_bands == [active.band]


def test_posture_uses_settings_band(rig: Rig) -> None:
    q.put_settings(rig.conn, {"posture_band": [150.0, 260.0]})
    rig.feed(sim_batches(1))
    rig.session.start(rig.check_id, "posture", "right")
    assert rig.session.active is not None and rig.session.active.band == (150.0, 260.0)


def test_posture_band_waits_for_first_valid_reading(rig: Rig) -> None:
    rig.session.start(rig.check_id, "posture", "right")
    active = rig.session.active
    assert active is not None and active.band is None
    rig.feed(sim_batches(1))
    assert active.band == pytest.approx((170.0, 230.0), abs=5.0)


def test_raw_samples_persisted(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "rest", "right")
    batches = sim_batches(10)
    rig.feed(batches)
    rig.session.stop(tid)
    raw = q.raw_for_test(rig.conn, tid)
    assert [s for s, _ in raw].count("imu") == 100 and [s for s, _ in raw].count("tof") == 100
    first_imu = next(p for s, p in raw if s == "imu")
    assert first_imu["t0"] == pytest.approx(DATA_T0) and len(first_imu["samples"]) == 10
    assert abs(first_imu["fs"] - 100.0) < 1


def test_tick_publishes_spectrum_during_rest(rig: Rig) -> None:
    rig.session.tick()
    assert rig.messages("spectrum") == []  # nothing recording
    rig.session.start(rig.check_id, "rest", "right")
    rig.feed(sim_batches(10))
    rig.session.tick()
    [spec] = rig.messages("spectrum")
    assert spec["peak_hz"] == 5.0 and max(spec["freqs"]) == 15.0
    call = rig.analysis.tremor_calls[-1]
    assert call["trim"] is False and call["n"] == 800
    rig.session.tick()
    assert rig.messages("spectrum") == []  # not due again at the same instant
    rig.clock.now += 0.25
    rig.session.tick()
    assert len(rig.messages("spectrum")) == 1


def test_tick_skips_spectrum_while_too_short(rig: Rig) -> None:
    rig.session.start(rig.check_id, "rest", "right")
    rig.feed(sim_batches(2))
    rig.session.tick()
    assert rig.messages("spectrum") == []


def test_tick_tolerates_unimplemented_analysis() -> None:
    rig = Rig(FakeAnalysis(unimplemented=True))
    rig.session.start(rig.check_id, "rest", "right")
    rig.feed(sim_batches(10))
    rig.session.tick()
    statuses = rig.messages("status")
    assert statuses[-1]["recording"] is True
    rig.session.tick()
    assert rig.messages("spectrum") == []


def test_status_messages_on_start_tick_and_stop(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "rest", "right")
    assert rig.messages("status") == [
        {
            "type": "status",
            "recording": True,
            "test_id": tid,
            "test_type": "rest",
            "seconds_left": None,
        }
    ]
    rig.clock.now += 1.0
    rig.session.tick()
    assert len(rig.messages("status")) == 1
    rig.clock.now += 0.5
    rig.session.tick()
    assert rig.messages("status") == []
    rig.session.stop(tid)
    [stopped] = rig.messages("status")
    assert stopped["recording"] is False and stopped["test_id"] is None


def test_tick_publishes_position_during_posture(rig: Rig) -> None:
    rig.feed(sim_batches(1))
    rig.session.start(rig.check_id, "posture", "right")
    rig.feed(sim_batches(3, t0=DATA_T0 + 1.0))
    rig.session.tick()
    [pos] = rig.messages("position")
    assert pos["in_band"] is True and pos["band"] == pytest.approx([170.0, 230.0], abs=5.0)
    assert 2.5 < pos["valid_seconds"] <= 3.0
    assert pos["tof_mm"] == pytest.approx(200.0, abs=5.0)
    rig.clock.now += 0.1
    rig.feed(sim_batches(0.2, SimParams(hand_mm=300.0), t0=DATA_T0 + 4.0))
    rig.session.tick()
    [pos] = rig.messages("position")
    assert pos["in_band"] is False and pos["tof_mm"] > 230.0


def test_no_position_messages_during_rest(rig: Rig) -> None:
    rig.session.start(rig.check_id, "rest", "right")
    rig.feed(sim_batches(1))
    rig.session.tick()
    assert rig.messages("position") == []


def test_recording_past_limit_is_interrupted_by_tick(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "rest", "right")
    rig.clock.now += MAX_RECORDING_S + 1
    rig.session.tick()
    assert rig.session.active is None
    row = q.get_test(rig.conn, tid)
    assert row is not None and (row.status, row.fail_reason) == ("failed", "interrupted")


def test_tap_start_creates_row_without_recording(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "tap", "left")
    assert rig.session.active is None
    row = q.get_test(rig.conn, tid)
    assert row is not None and row.type == "tap" and row.status == "recording"
    rig.session.start(rig.check_id, "tap", "right")  # a pending tap row never blocks
    with pytest.raises(InvalidStateError):
        rig.session.stop(tid)


def test_start_unknown_check_is_not_found(rig: Rig) -> None:
    with pytest.raises(NotFoundError):
        rig.session.start(999, "rest", "right")


def test_stop_and_mark_unknown_test_are_not_found(rig: Rig) -> None:
    with pytest.raises(NotFoundError):
        rig.session.stop(999)
    with pytest.raises(NotFoundError):
        rig.session.mark(999)


def test_stop_twice_is_invalid_state(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "rest", "right")
    rig.feed(sim_batches(10))
    rig.session.stop(tid)
    with pytest.raises(InvalidStateError):
        rig.session.stop(tid)
    with pytest.raises(InvalidStateError):
        rig.session.mark(tid)


def test_mark_stores_markers_with_the_test(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "rest", "right")
    rig.feed(sim_batches(3))
    rig.session.mark(tid)
    marked_at = rig.clock.now
    rig.feed(sim_batches(7, t0=DATA_T0 + 3.0))
    rig.session.stop(tid)
    row = q.get_test(rig.conn, tid)
    assert row is not None and row.markers == [marked_at]


def test_unimplemented_analysis_stores_failed_and_frees_session() -> None:
    rig = Rig(FakeAnalysis(unimplemented=True))
    tid = rig.session.start(rig.check_id, "rest", "right")
    rig.feed(sim_batches(10))
    with pytest.raises(AnalysisUnavailableError):
        rig.session.stop(tid)
    row = q.get_test(rig.conn, tid)
    assert row is not None and (row.status, row.fail_reason) == ("failed", "interrupted")
    assert len(q.raw_for_test(rig.conn, tid)) == 200
    assert rig.session.active is None
    rig.session.start(rig.check_id, "rest", "right")


def test_listener_detached_after_stop(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "rest", "right")
    active = rig.session.active
    assert active is not None
    rig.feed(sim_batches(10))
    rig.session.stop(tid)
    n = len(active.imu()[0])
    rig.feed(sim_batches(1, t0=DATA_T0 + 20))
    assert len(active.imu()[0]) == n


def test_now_is_utc_from_clock(rig: Rig) -> None:
    assert rig.session.now().timestamp() == pytest.approx(DATA_T0)
    assert rig.session.now().utcoffset() is not None


def test_tick_posture_spectrum_uses_posture_gate(rig: Rig) -> None:
    # The fake reports 0.2 m/s², above the rest gate but below the posture gate.
    rig.session.start(rig.check_id, "posture", "right")
    rig.feed(sim_batches(10))
    rig.session.tick()
    [spec] = rig.messages("spectrum")
    assert spec["peak_hz"] is None
