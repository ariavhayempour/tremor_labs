"""Simulated IMU (100 Hz) and ToF (40 Hz) source for development without hardware."""

import asyncio
import dataclasses
import math
import time
from collections import deque
from collections.abc import AsyncIterator

import numpy as np
from numpy.typing import NDArray

from tremorlab.config import SimParams
from tremorlab.sources.base import (
    Batch,
    ImuBatch,
    LedCommand,
    SourceHealth,
    SourceStatus,
    TofBatch,
)

IMU_HZ = 100.0
TOF_HZ = 40.0
BATCH_S = 0.1
GRAVITY_MS2 = 9.81
AXIS_WEIGHTS = np.array([0.6, 0.6, 0.5])
DRIFT_HZ = 0.05
DRIFT_MS2 = 0.05
GYRO_DPS_PER_MS2 = 10.0
GYRO_NOISE_DPS = 0.3
TOF_NOISE_MM = 1.0
DESCENT_FROM_MM = 300.0
DESCENT_TO_MM = 30.0
DESCENT_S = 2.5
DESCENT_HOLD_S = 1.0
WOBBLE_HZ = 8.0
WOBBLE_ZONE_MM = 50.0
HEALTH_WINDOW_S = 5.0
SENSORS = {"movement": True, "distance": True}


def measured_rate(ts: deque[float]) -> float | None:
    """Samples per second over the last HEALTH_WINDOW_S of timestamps, None if unknown."""
    if len(ts) < 2:
        return None
    arr = np.fromiter(ts, dtype=np.float64)
    arr = arr[arr >= arr[-1] - HEALTH_WINDOW_S]
    span = float(arr[-1] - arr[0])
    return (len(arr) - 1) / span if span > 0 else None


def _min_jerk(p: NDArray[np.float64]) -> NDArray[np.float64]:
    return 10 * p**3 - 15 * p**4 + 6 * p**5


class SimulatedSource:
    name = "sim"

    def __init__(self, params: SimParams, *, fast: bool = False, seed: int | None = None) -> None:
        self._params = params
        self._fast = fast
        self._rng = np.random.default_rng(seed)
        self._running = False
        self._t0: float | None = None
        self._mono0 = 0.0
        self._batch = 0
        self._phase = 0.0
        self._descent_pending = False
        self._descent_start: float | None = None
        self._status_sent = False
        self._imu_ts: deque[float] = deque(maxlen=int(IMU_HZ * (HEALTH_WINDOW_S + 1)))
        self._tof_ts: deque[float] = deque(maxlen=int(TOF_HZ * (HEALTH_WINDOW_S + 1)))

    @property
    def params(self) -> SimParams:
        return self._params

    def set_params(self, **changes: float) -> SimParams:
        """Apply changes from the next batch on; returns the new params."""
        known = {f.name for f in dataclasses.fields(SimParams)}
        unknown = set(changes) - known
        if unknown:
            raise ValueError(f"unknown simulator parameters: {sorted(unknown)}")
        self._params = dataclasses.replace(
            self._params, **{k: float(v) for k, v in changes.items()}
        )
        return self._params

    def trigger_descent(self) -> None:
        """Script a 300 → 30 mm ToF descent over 2.5 s, with reach_wobble in the last 50 mm."""
        self._descent_pending = True

    async def start(self) -> None:
        self._running = True
        if self._t0 is None:
            self._t0 = time.time()
            self._mono0 = time.monotonic()

    async def stop(self) -> None:
        self._running = False

    async def batches(self) -> AsyncIterator[Batch]:
        if self._t0 is None:
            await self.start()
        self._running = True
        if not self._status_sent:
            self._status_sent = True
            yield SourceStatus(connected=True, sensors=dict(SENSORS))
        while self._running:
            if self._fast:
                await asyncio.sleep(0)  # let other tasks run between generated batches
            else:
                deadline = self._mono0 + (self._batch + 1) * BATCH_S
                await asyncio.sleep(max(0.0, deadline - time.monotonic()))
            if not self._running:
                return
            imu, tof = self._next_batches()
            yield imu
            yield tof

    async def led(self, command: LedCommand, value: int | None) -> None:
        return None

    def health(self) -> SourceHealth:
        return SourceHealth(
            connected=True,
            sensors_detected=dict(SENSORS),
            imu_hz=measured_rate(self._imu_ts),
            tof_hz=measured_rate(self._tof_ts),
        )

    def _next_batches(self) -> tuple[ImuBatch, TofBatch]:
        assert self._t0 is not None
        k = self._batch
        self._batch += 1
        p = self._params
        n_imu = round(IMU_HZ * BATCH_S)
        t_rel = np.arange(k * n_imu, (k + 1) * n_imu) / IMU_HZ
        step = 2 * math.pi * p.tremor_hz / IMU_HZ
        phases = self._phase + step * np.arange(n_imu)
        self._phase = float((phases[-1] + step) % (2 * math.pi))
        tremor = np.sin(phases)[:, None] * AXIS_WEIGHTS[None, :]
        drift = DRIFT_MS2 * np.sin(2 * math.pi * DRIFT_HZ * t_rel)[:, None]
        acc = p.tremor_amp * tremor + drift + self._rng.normal(0.0, p.noise, (n_imu, 3))
        acc[:, 2] += GRAVITY_MS2
        gyro = GYRO_DPS_PER_MS2 * p.tremor_amp * tremor + self._rng.normal(
            0.0, GYRO_NOISE_DPS, (n_imu, 3)
        )
        t_imu = self._t0 + t_rel

        n_tof = round(TOF_HZ * BATCH_S)
        t_tof = self._t0 + np.arange(k * n_tof, (k + 1) * n_tof) / TOF_HZ
        mm = self._tof_values(t_tof) + self._rng.normal(0.0, TOF_NOISE_MM, n_tof)

        self._imu_ts.extend(t_imu.tolist())
        self._tof_ts.extend(t_tof.tolist())
        return ImuBatch(t=t_imu, acc=acc, gyro=gyro), TofBatch(t=t_tof, mm=mm)

    def _tof_values(self, t: NDArray[np.float64]) -> NDArray[np.float64]:
        """Noise-free hand height in mm at times t, following any scripted descent."""
        if self._descent_pending:
            self._descent_pending = False
            self._descent_start = float(t[0])
        mm = np.full(t.shape, self._params.hand_mm)
        if self._descent_start is None:
            return mm
        rel = t - self._descent_start
        if rel[0] > DESCENT_S + DESCENT_HOLD_S:
            self._descent_start = None
            return mm
        moving = rel <= DESCENT_S
        progress = np.clip(rel / DESCENT_S, 0.0, 1.0)
        path = DESCENT_FROM_MM - (DESCENT_FROM_MM - DESCENT_TO_MM) * _min_jerk(progress)
        wobble_zone = moving & (path < DESCENT_TO_MM + WOBBLE_ZONE_MM)
        wobble = self._params.reach_wobble * np.sin(2 * math.pi * WOBBLE_HZ * rel)
        path = path + np.where(wobble_zone, wobble, 0.0)
        return np.where(rel <= DESCENT_S + DESCENT_HOLD_S, path, mm)
