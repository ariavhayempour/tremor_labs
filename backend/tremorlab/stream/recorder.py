"""Collects the batches of one recording test and derives its live posture state."""

import math
from collections.abc import Callable, Iterator
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from tremorlab.analysis.posture import TOF_MATCH_MAX_S, TOF_VALID_RANGE_MM
from tremorlab.db.models import TestType
from tremorlab.sources.base import Batch, ImuBatch, TofBatch
from tremorlab.stream.messages import Message, imu_msg, tof_msg

Band = tuple[float, float]


def valid_mm(mm: float) -> bool:
    """A usable ToF reading: finite and inside TOF_VALID_RANGE_MM."""
    return math.isfinite(mm) and TOF_VALID_RANGE_MM[0] <= mm <= TOF_VALID_RANGE_MM[1]


class Recorder:
    """started_at is the session clock (epoch s) at start; band is mm, or set by band_from."""

    def __init__(
        self,
        test_id: int,
        kind: TestType,
        started_at: float,
        band: Band | None,
        *,
        band_from: Callable[[float], Band] | None = None,
    ) -> None:
        self.test_id = test_id
        self.kind = kind
        self.started_at = started_at
        self.band = band
        self._band_from = band_from
        self._batches: list[ImuBatch | TofBatch] = []
        self._imu: list[ImuBatch] = []
        self._tof: list[TofBatch] = []
        self._markers: list[float] = []
        self._valid_seconds = 0.0
        self._prev_in_band_t: float | None = None

    def add(self, b: Batch) -> None:
        if isinstance(b, ImuBatch) and len(b.t):
            self._batches.append(b)
            self._imu.append(b)
        elif isinstance(b, TofBatch) and len(b.t):
            self._batches.append(b)
            self._tof.append(b)
            self._track_position(b)

    def _track_position(self, b: TofBatch) -> None:
        for t, mm in zip(b.t.tolist(), b.mm.tolist(), strict=True):
            if not valid_mm(mm):
                self._prev_in_band_t = None
                continue
            if self.band is None and self._band_from is not None:
                self.band = self._band_from(mm)
            if self.band is None or not self.band[0] <= mm <= self.band[1]:
                self._prev_in_band_t = None
                continue
            prev = self._prev_in_band_t
            if prev is not None and 0 < t - prev <= TOF_MATCH_MAX_S:
                self._valid_seconds += t - prev
            self._prev_in_band_t = t

    def imu(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """(t (N,) s, acc (N, 3) m/s²) over the whole recording."""
        if not self._imu:
            return np.empty(0), np.empty((0, 3))
        return np.concatenate([b.t for b in self._imu]), np.vstack([b.acc for b in self._imu])

    def imu_window(self, seconds: float) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """IMU samples within `seconds` before the newest one."""
        if not self._imu:
            return self.imu()
        newest = float(self._imu[-1].t[-1])
        recent: list[ImuBatch] = []
        for b in reversed(self._imu):
            recent.append(b)
            if b.t[0] <= newest - seconds:
                break
        t = np.concatenate([b.t for b in reversed(recent)])
        acc = np.vstack([b.acc for b in reversed(recent)])
        keep = t > newest - seconds
        return t[keep], acc[keep]

    def tof(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """(t (N,) s, mm (N,)) including invalid (NaN) readings."""
        if not self._tof:
            return np.empty(0), np.empty(0)
        return np.concatenate([b.t for b in self._tof]), np.concatenate([b.mm for b in self._tof])

    def latest_tof(self) -> float | None:
        """Newest ToF reading in mm, None when it is invalid or absent."""
        if not self._tof:
            return None
        mm = float(self._tof[-1].mm[-1])
        return mm if valid_mm(mm) else None

    @property
    def valid_seconds(self) -> float:
        """In-band time so far in s, counting gaps up to TOF_MATCH_MAX_S between readings."""
        return self._valid_seconds

    def raw_payloads(self) -> Iterator[tuple[Literal["imu", "tof"], Message]]:
        """The WebSocket message dict of every batch, in arrival order; empty ToF skipped."""
        imu_fs: float | None = None
        tof_fs: float | None = None
        for b in self._batches:
            if isinstance(b, ImuBatch):
                msg = imu_msg(b, fallback_fs=imu_fs)
                imu_fs = msg["fs"]
                yield "imu", msg
            else:
                msg = tof_msg(b, fallback_fs=tof_fs)
                if msg["samples_mm"]:
                    tof_fs = msg["fs"]
                    yield "tof", msg

    def mark(self, t: float) -> None:
        self._markers.append(t)

    @property
    def markers(self) -> list[float]:
        return list(self._markers)
