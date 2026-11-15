import asyncio
import dataclasses
import math
from collections.abc import Iterator

import numpy as np
import pytest

from tests.api.fakes import DATA_T0, REACH_MM, FakeAnalysis, sim_batches
from tests.test_session import Rig
from tremorlab.analysis.tap import TapFrame
from tremorlab.config import SimParams
from tremorlab.db import queries as q
from tremorlab.session import (
    MAX_CURVE_POINTS,
    AnalysisUnavailableError,
    InvalidStateError,
    NotFoundError,
)
from tremorlab.sources.base import ImuBatch, TofBatch
from tremorlab.sources.simulated import SimulatedSource

Segment = list[ImuBatch | TofBatch]


@pytest.fixture
def rig() -> Iterator[Rig]:
    r = Rig()
    yield r
    r.conn.close()


def descent_segments(
    n: int, seconds: float, *, wobble: float = 0.0, t0: float = DATA_T0
) -> list[Segment]:
    """n consecutive sim segments of `seconds`, each starting with a scripted descent."""
    source = SimulatedSource(SimParams(reach_wobble=wobble), fast=True, seed=1)

    async def take(n_pairs: int) -> Segment:
        out: Segment = []
        async for b in source.batches():
            if isinstance(b, ImuBatch | TofBatch):
                out.append(b)
            if len(out) >= 2 * n_pairs:
                break
        return out

    segments = []
    for _ in range(n):
        source.trigger_descent()
        segments.append(asyncio.run(take(round(seconds * 10))))
    shift = t0 - float(segments[0][0].t[0])
    return [[dataclasses.replace(b, t=b.t + shift) for b in seg] for seg in segments]


def record_reach(rig: Rig, segments: list[Segment]) -> tuple[int, list[float]]:
    """Start a reach test, feed segments with a mark between each; returns (test id, marks)."""
    tid = rig.session.start(rig.check_id, "reach", "right")
    marks = []
    for i, seg in enumerate(segments):
        if i:
            rig.session.mark(tid)
            marks.append(rig.clock.now)
        rig.feed(seg)
    return tid, marks


def frames(n: int = 40, *, fps: float = 30.0, t0: float = 12.0) -> list[TapFrame]:
    """n frames with a hand, an index finger opening and closing at about 4 Hz."""
    out = []
    for i in range(n):
        t = t0 + i / fps
        x = 0.4 + 0.05 * (1 + math.sin(2 * math.pi * 4 * t))  # thumb-index gap 0..0.1
        out.append(TapFrame(t, ((0.5, 0.8), (0.4, 0.4), (x, 0.4), (0.5, 0.5))))
    return out


def test_reach_session_with_marks_uses_three_attempts(rig: Rig) -> None:
    tid, marks = record_reach(rig, descent_segments(3, 6.0))
    out = rig.session.stop(tid)
    assert out.status == "done" and out.fail_reason is None and out.result is not None
    assert out.result.smoothness == REACH_MM and out.result.wobble_ratio == 1.0
    assert out.result.strength_score is None and out.result.taps_per_sec is None
    [call] = rig.analysis.reach_calls
    assert call["marks"] == marks and len(marks) == 2 and call["n"] == 3 * 6 * 40
    attempts = out.result.details["attempts"]
    assert len(attempts) == 3
    for a in attempts:
        assert set(a) == {"t", "mm", "residual"}
        assert len(a["t"]) == len(a["mm"]) == len(a["residual"]) == MAX_CURVE_POINTS
        assert a["t"][0] == 0.0 and a["t"] == sorted(a["t"])
        assert a["t"][-1] == pytest.approx(6.0, abs=0.05)
    stored = q.get_result(rig.conn, tid)
    assert stored is not None and stored.details == out.result.details
    row = q.get_test(rig.conn, tid)
    assert row is not None and row.status == "done" and row.markers == marks
    assert {s for s, _ in q.raw_for_test(rig.conn, tid)} == {"imu", "tof"}


def test_reach_short_attempts_are_not_downsampled(rig: Rig) -> None:
    tid, _ = record_reach(rig, descent_segments(1, 4.0))
    out = rig.session.stop(tid)
    assert out.result is not None
    [a] = out.result.details["attempts"]
    assert len(a["t"]) == 4 * 40 and a["t"][1] == pytest.approx(0.025)


def test_reach_without_descent_fails_no_descent_detected(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "reach", "right")
    rig.feed(sim_batches(5))
    out = rig.session.stop(tid)
    assert (out.status, out.fail_reason, out.result) == ("failed", "no_descent_detected", None)
    row = q.get_test(rig.conn, tid)
    assert row is not None and (row.status, row.fail_reason) == ("failed", "no_descent_detected")


def test_reach_without_tof_fails_no_descent_detected(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "reach", "right")
    rig.feed([b for b in sim_batches(5) if isinstance(b, ImuBatch)])
    out = rig.session.stop(tid)
    assert (out.status, out.fail_reason) == ("failed", "no_descent_detected")
    assert rig.analysis.reach_calls == []


def test_reach_gap_fails_with_sensor_disconnected(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "reach", "right")
    rig.feed(sim_batches(3))
    rig.feed(sim_batches(3, t0=DATA_T0 + 5.0))
    assert rig.session.stop(tid).fail_reason == "sensor_disconnected"


def test_reach_unimplemented_analysis_is_unavailable() -> None:
    rig = Rig(FakeAnalysis(unimplemented=True))
    tid = rig.session.start(rig.check_id, "reach", "right")
    rig.feed(sim_batches(5))
    with pytest.raises(AnalysisUnavailableError):
        rig.session.stop(tid)
    row = q.get_test(rig.conn, tid)
    assert row is not None and (row.status, row.fail_reason) == ("failed", "interrupted")
    assert rig.session.active is None


def test_tap_submit_stores_result(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "tap", "left")
    submitted = frames()
    submitted[0] = TapFrame(submitted[0].t, None)
    out = rig.session.submit_tap(tid, submitted)
    assert out.status == "done" and out.fail_reason is None and out.result is not None
    r = out.result
    assert (r.taps_per_sec, r.tap_amplitude, r.amplitude_decrement, r.rhythm_cv) == (
        4.0,
        0.5,
        -0.1,
        0.05,
    )
    assert r.smoothness is None and r.strength_score is None
    assert set(r.details) == {"t", "signal", "peaks"}
    assert len(r.details["t"]) == len(r.details["signal"]) == 39
    assert r.details["t"][0] == pytest.approx(1 / 30, abs=1e-3)  # seconds from the first frame
    assert r.details["peaks"] == list(range(0, 39, 2))
    stored = q.get_result(rig.conn, tid)
    assert stored is not None and stored.taps_per_sec == 4.0 and stored.details == r.details
    row = q.get_test(rig.conn, tid)
    assert row is not None and row.status == "done" and row.ended_at is not None


def test_tap_submit_sorts_frames_by_time(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "tap", "right")
    rig.session.submit_tap(tid, list(reversed(frames())))
    [call] = rig.analysis.tap_calls
    times = [f.t for f in call]
    assert times == sorted(times)


def test_tap_without_hand_frames_fails_no_taps(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "tap", "right")
    out = rig.session.submit_tap(tid, [TapFrame(f.t, None) for f in frames()])
    assert (out.status, out.fail_reason, out.result) == ("failed", "no_taps_detected", None)
    tid2 = rig.session.start(rig.check_id, "tap", "left")
    assert rig.session.submit_tap(tid2, []).fail_reason == "no_taps_detected"
    row = q.get_test(rig.conn, tid2)
    assert row is not None and (row.status, row.fail_reason) == ("failed", "no_taps_detected")


def test_tap_submit_twice_is_invalid_state(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "tap", "right")
    rig.session.submit_tap(tid, frames())
    with pytest.raises(InvalidStateError):
        rig.session.submit_tap(tid, frames())


def test_tap_submit_on_non_tap_test_is_invalid_state(rig: Rig) -> None:
    tid = rig.session.start(rig.check_id, "rest", "right")
    with pytest.raises(InvalidStateError):
        rig.session.submit_tap(tid, frames())
    assert rig.session.active is not None and rig.session.active.test_id == tid


def test_tap_submit_unknown_test_is_not_found(rig: Rig) -> None:
    with pytest.raises(NotFoundError):
        rig.session.submit_tap(999, frames())


def test_tap_unimplemented_analysis_is_unavailable() -> None:
    rig = Rig(FakeAnalysis(unimplemented=True))
    tid = rig.session.start(rig.check_id, "tap", "right")
    with pytest.raises(AnalysisUnavailableError):
        rig.session.submit_tap(tid, frames())
    row = q.get_test(rig.conn, tid)
    assert row is not None and (row.status, row.fail_reason) == ("failed", "interrupted")


@pytest.mark.integration
def test_reach_session_real_analysis_three_attempts() -> None:
    rig = Rig(real=True)
    tid, _ = record_reach(rig, descent_segments(3, 5.0))
    out = rig.session.stop(tid)
    assert out.status == "done" and out.result is not None
    assert out.result.smoothness is not None and np.isfinite(out.result.smoothness)
    assert len(out.result.details["attempts"]) == 3


@pytest.mark.integration
def test_tap_session_real_analysis_recovers_rate() -> None:
    rig = Rig(real=True)
    tid = rig.session.start(rig.check_id, "tap", "right")
    out = rig.session.submit_tap(tid, frames(300))
    assert out.status == "done" and out.result is not None
    assert out.result.taps_per_sec == pytest.approx(4.0, abs=0.3)
