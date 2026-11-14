"""Recording lifecycle: one active sensor recording at a time, analysis on stop, live messages."""

import asyncio
import dataclasses
import logging
import sqlite3
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from tremorlab.analysis import Analyzers
from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.posture import BAND_HALF_WIDTH_MM, analyze_posture
from tremorlab.analysis.reach import ReachAttempt, ReachResult, analyze_reach
from tremorlab.analysis.tap import MIN_TAPS, TapFrame, TapResult, analyze_taps
from tremorlab.analysis.tremor import TremorResult, analyze_tremor
from tremorlab.api.schemas import ResultOut
from tremorlab.db import queries
from tremorlab.db.models import FailReason, Hand, ResultRow, TestType
from tremorlab.sources.base import SensorSource
from tremorlab.stream.broadcaster import Broadcaster
from tremorlab.stream.messages import (
    position_msg,
    round_sig,
    spectrum_msg,
    spectrum_payload,
    status_msg,
)
from tremorlab.stream.recorder import Band, Recorder, valid_mm

STALE_AFTER_S = 120.0
MAX_GAP_S = 1.0
MAX_RECORDING_S = 600.0
LIVE_WINDOW_S = 8.0
SPECTRUM_EVERY_S = 0.25
POSITION_EVERY_S = 0.1
STATUS_EVERY_S = 1.0
TICK_S = 0.05
BAND_LOOKBACK_S = 1.0
SPECTRUM_KINDS: tuple[TestType, ...] = ("rest", "posture")
MAX_CURVE_POINTS = 200
CURVE_T_DECIMALS = 3

log = logging.getLogger(__name__)


class ActiveTestError(Exception):
    """Another test has been recording for less than STALE_AFTER_S."""


class InvalidStateError(Exception):
    """The test exists but is not the active recording."""


class NotFoundError(LookupError):
    """Unknown check or test id."""


class AnalysisUnavailableError(Exception):
    """The analyzer for this test type is not implemented yet."""


@dataclass(frozen=True)
class TestOutcome:
    __test__ = False  # not a pytest test class

    test_id: int
    status: Literal["done", "failed"]
    fail_reason: FailReason | None
    result: ResultOut | None


def default_analyzers() -> Analyzers:
    return Analyzers(
        tremor=analyze_tremor, posture=analyze_posture, reach=analyze_reach, tap=analyze_taps
    )


DEFAULT_ANALYZERS = default_analyzers()


def band_around(start_mm: float) -> Band:
    """Start height ± BAND_HALF_WIDTH_MM, in mm."""
    return (start_mm - BAND_HALF_WIDTH_MM, start_mm + BAND_HALF_WIDTH_MM)


def largest_gap(t: NDArray[np.float64]) -> float:
    """Largest spacing between consecutive timestamps in s (0 for fewer than 2)."""
    return float(np.max(np.diff(t))) if len(t) >= 2 else 0.0


def tremor_row(r: TremorResult) -> ResultRow:
    return ResultRow(
        peak_hz=None if r.peak_hz is None else float(r.peak_hz),
        strength_ms2=float(r.strength_ms2),
        strength_score=float(r.strength_score),
        tremor_detected=bool(r.tremor_detected),
        valid_seconds=float(r.valid_seconds),
        details=dict(spectrum_payload(r.freqs, r.psd)),
    )


def finite_or_none(x: float) -> float | None:
    return float(x) if np.isfinite(x) else None


def downsample_idx(n: int, max_points: int = MAX_CURVE_POINTS) -> NDArray[np.int64]:
    """At most max_points evenly spaced indices into n samples, always keeping both ends."""
    if n <= max_points:
        return np.arange(n, dtype=np.int64)
    return np.unique(np.round(np.linspace(0, n - 1, max_points)).astype(np.int64))


def rel_times(t: NDArray[np.float64], t0: float) -> list[float]:
    """Seconds from t0, rounded to milliseconds."""
    return [float(v) for v in np.round(t - t0, CURVE_T_DECIMALS).tolist()]


def attempt_curve(a: ReachAttempt) -> dict[str, list[float]]:
    """{"t" s from attempt start, "mm", "residual" mm}, finite points only, downsampled."""
    t, mm, residual = (np.asarray(x, dtype=np.float64) for x in (a.t, a.mm, a.residual))
    keep = np.flatnonzero(np.isfinite(t) & np.isfinite(mm) & np.isfinite(residual))
    if len(keep) == 0:
        return {"t": [], "mm": [], "residual": []}
    idx = keep[downsample_idx(len(keep))]
    return {
        "t": rel_times(t[idx], float(t[keep[0]])),
        "mm": round_sig(mm[idx]),
        "residual": round_sig(residual[idx]),
    }


def reach_row(r: ReachResult) -> ResultRow:
    return ResultRow(
        smoothness=finite_or_none(r.smoothness_mm),
        wobble_ratio=finite_or_none(r.wobble_ratio),
        details={"attempts": [attempt_curve(a) for a in r.attempts]},
    )


def tap_row(r: TapResult, t_first: float) -> ResultRow:
    """details t is seconds from the first submitted frame; peaks index into signal."""
    return ResultRow(
        taps_per_sec=finite_or_none(r.taps_per_sec),
        tap_amplitude=finite_or_none(r.amplitude),
        amplitude_decrement=finite_or_none(r.decrement),
        rhythm_cv=finite_or_none(r.rhythm_cv),
        details={
            "t": rel_times(np.asarray(r.t, dtype=np.float64), t_first),
            "signal": round_sig(np.asarray(r.signal, dtype=np.float64)),
            "peaks": [int(i) for i in np.asarray(r.peak_idx).tolist()],
        },
    )


def result_out(row: ResultRow) -> ResultOut:
    return ResultOut(**dataclasses.asdict(row))


class TestSession:
    __test__ = False  # not a pytest test class

    def __init__(
        self,
        conn: sqlite3.Connection,
        broadcaster: Broadcaster,
        source: SensorSource,
        *,
        analyzers: Analyzers = DEFAULT_ANALYZERS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.conn = conn
        self.broadcaster = broadcaster
        self.source = source
        self.analyzers = analyzers
        self.clock = clock
        self._active: Recorder | None = None
        self._due: dict[str, float] = {}

    @property
    def active(self) -> Recorder | None:
        return self._active

    def now(self) -> datetime:
        return datetime.fromtimestamp(self.clock(), UTC)

    def start(self, check_id: int, type: TestType, hand: Hand) -> int:
        """Insert the test row; rest/posture/reach also start recording. Returns the test id."""
        if queries.get_check(self.conn, check_id) is None:
            raise NotFoundError(f"check {check_id}")
        now = self.clock()
        if self._active is not None:
            if now - self._active.started_at < STALE_AFTER_S:
                raise ActiveTestError(f"test {self._active.test_id} is recording")
            self._interrupt()
        stale_before = self.now() - timedelta(seconds=STALE_AFTER_S)
        queries.fail_stale_recordings(self.conn, older_than=stale_before)
        test_id = queries.insert_test(
            self.conn, check_id=check_id, type=type, hand=hand, started_at=self.now()
        )
        if type == "tap":
            return test_id
        band = self._posture_band() if type == "posture" else None
        band_from = band_around if type == "posture" and band is None else None
        self._active = Recorder(test_id, type, now, band, band_from=band_from)
        self._due = {"status": now}
        self.broadcaster.set_listener(self._active.add)
        self.broadcaster.publish(status_msg(True, test_id, type))
        return test_id

    def stop(self, test_id: int) -> TestOutcome:
        """Save raw batches and analyze; analysis failures become a stored failed test."""
        rec = self._require_active(test_id)
        self._detach()
        try:
            for sensor, payload in rec.raw_payloads():
                queries.insert_raw(self.conn, test_id, sensor, payload)
            row, fail_reason = self._analyze(rec)
        except NotImplementedError as e:
            self._finish(test_id, "failed", "interrupted", rec.markers)
            raise AnalysisUnavailableError(f"{rec.kind} analysis is not available yet") from e
        except Exception:
            self._finish(test_id, "failed", "interrupted", rec.markers)
            raise
        return self._store(test_id, row, fail_reason, rec.markers)

    def submit_tap(self, test_id: int, frames: Sequence[TapFrame]) -> TestOutcome:
        """Analyze the browser's landmark frames for a tap test that is still recording."""
        row = queries.get_test(self.conn, test_id)
        if row is None:
            raise NotFoundError(f"test {test_id}")
        if row.type != "tap" or row.status != "recording":
            raise InvalidStateError(f"test {test_id} is not an open tap test")
        ordered = sorted(frames, key=lambda f: f.t)
        try:
            result, fail_reason = self._analyze_tap(ordered)
        except NotImplementedError as e:
            self._finish(test_id, "failed", "interrupted")
            raise AnalysisUnavailableError("tap analysis is not available yet") from e
        except Exception:
            self._finish(test_id, "failed", "interrupted")
            raise
        return self._store(test_id, result, fail_reason)

    def mark(self, test_id: int) -> None:
        """Record a reach-attempt boundary at the current clock time."""
        self._require_active(test_id).mark(self.clock())

    def tick(self) -> None:
        """Publish whatever live messages are due for the active recording."""
        rec = self._active
        if rec is None:
            return
        now = self.clock()
        if now - rec.started_at > MAX_RECORDING_S:
            self._interrupt()
            return
        if rec.kind in SPECTRUM_KINDS and self._is_due("spectrum", now, SPECTRUM_EVERY_S):
            self._publish_spectrum(rec)
        band = rec.band
        if rec.kind == "posture" and band and self._is_due("position", now, POSITION_EVERY_S):
            mm = rec.latest_tof()
            in_band = mm is not None and band[0] <= mm <= band[1]
            self.broadcaster.publish(position_msg(mm, in_band, band, rec.valid_seconds))
        if self._is_due("status", now, STATUS_EVERY_S):
            self.broadcaster.publish(status_msg(True, rec.test_id, rec.kind))

    async def run(self) -> None:
        """Call tick() every TICK_S until cancelled."""
        while True:
            try:
                self.tick()
            except Exception:
                log.exception("session tick failed")
            await asyncio.sleep(TICK_S)

    def _is_due(self, key: str, now: float, every: float) -> bool:
        if now - self._due.get(key, -np.inf) < every:
            return False
        self._due[key] = now
        return True

    def _publish_spectrum(self, rec: Recorder) -> None:
        t, acc = rec.imu_window(LIVE_WINDOW_S)
        if len(t) < 2:
            return
        try:
            r = self.analyzers.tremor(t, acc, trim=False)
        except (AnalysisError, NotImplementedError):
            return
        self.broadcaster.publish(spectrum_msg(r.freqs, r.psd, r.peak_hz))

    def _store(
        self,
        test_id: int,
        row: ResultRow | None,
        fail_reason: FailReason | None,
        markers: list[float] | None = None,
    ) -> TestOutcome:
        if row is None:
            self._finish(test_id, "failed", fail_reason, markers)
            return TestOutcome(test_id, "failed", fail_reason, None)
        queries.insert_result(self.conn, test_id, row)
        self._finish(test_id, "done", None, markers)
        return TestOutcome(test_id, "done", None, result_out(row))

    def _analyze_tap(
        self, frames: Sequence[TapFrame]
    ) -> tuple[ResultRow | None, FailReason | None]:
        if sum(f.lm is not None for f in frames) < MIN_TAPS:
            return None, "no_taps_detected"
        try:
            return tap_row(self.analyzers.tap(list(frames)), frames[0].t), None
        except AnalysisError as e:
            return None, e.code

    def _analyze(self, rec: Recorder) -> tuple[ResultRow | None, FailReason | None]:
        t, acc = rec.imu()
        no_data = len(t) < 2 and self.clock() - rec.started_at > MAX_GAP_S
        if no_data or largest_gap(t) > MAX_GAP_S:
            return None, "sensor_disconnected"
        try:
            if rec.kind == "rest":
                return tremor_row(self.analyzers.tremor(t, acc)), None
            if rec.kind == "posture":
                if rec.band is None:
                    raise AnalysisError("insufficient_valid_data")
                t_tof, mm = rec.tof()
                return tremor_row(self.analyzers.posture(t, acc, t_tof, mm, rec.band)), None
            if rec.kind == "reach":
                t_tof, mm = rec.tof()
                if np.count_nonzero(np.isfinite(mm)) < 2:
                    raise AnalysisError("no_descent_detected")
                return reach_row(self.analyzers.reach(t_tof, mm, rec.markers)), None
            raise ValueError(f"no sensor analysis for {rec.kind} tests")
        except AnalysisError as e:
            return None, e.code

    def _posture_band(self) -> Band | None:
        stored = queries.get_settings(self.conn).get("posture_band")
        if stored is not None:
            return (float(stored[0]), float(stored[1]))
        _, mm = self.broadcaster.tof_ring.window(BAND_LOOKBACK_S)
        valid = [v for v in mm.tolist() if valid_mm(v)]
        return band_around(valid[-1]) if valid else None

    def _require_active(self, test_id: int) -> Recorder:
        if self._active is not None and self._active.test_id == test_id:
            return self._active
        if queries.get_test(self.conn, test_id) is None:
            raise NotFoundError(f"test {test_id}")
        raise InvalidStateError(f"test {test_id} is not recording")

    def _detach(self) -> None:
        self.broadcaster.set_listener(None)
        self._active = None
        self.broadcaster.publish(status_msg(False, None, None))

    def _finish(
        self,
        test_id: int,
        status: Literal["done", "failed"],
        fail_reason: FailReason | None,
        markers: list[float] | None = None,
    ) -> None:
        queries.finish_test(
            self.conn,
            test_id,
            ended_at=self.now(),
            status=status,
            fail_reason=fail_reason,
            markers=markers,
        )

    def _interrupt(self) -> None:
        rec = self._active
        if rec is None:
            return
        self._detach()
        self._finish(rec.test_id, "failed", "interrupted", rec.markers)
