"""ReplaySource: re-emits stored raw_samples in real time, shifted to now, looping."""

import asyncio
import sqlite3
import time
from collections import deque
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from tremorlab.config import Config
from tremorlab.db import queries
from tremorlab.db.connection import connect
from tremorlab.db.models import Sensor
from tremorlab.sources.base import (
    Batch,
    ImuBatch,
    LedCommand,
    SourceHealth,
    SourceStatus,
    TofBatch,
)
from tremorlab.sources.simulated import SENSORS, measured_rate

LOOP_GAP_S = 0.1  # pause between replayed tests and between loops, one batch interval
RATE_HISTORY = 2000  # timestamps kept per sensor for health(); covers its 5 s window


@dataclass(frozen=True)
class _Item:
    """One stored batch; t is seconds from the start of the replay timeline."""

    t: NDArray[np.float64]
    imu: NDArray[np.float64] | None
    mm: NDArray[np.float64] | None


def _parse(sensor: Sensor, p: dict[str, Any]) -> tuple[NDArray[np.float64], _Item] | None:
    """(epoch s timestamps, item with those timestamps) of one stored payload, None if empty."""
    t0, fs = float(p["t0"]), float(p["fs"])
    if sensor == "imu":
        samples = np.asarray(p["samples"], dtype=np.float64).reshape(-1, 6)
        if not len(samples):
            return None
        t = t0 + np.arange(len(samples)) / fs
        return t, _Item(t, samples, None)
    mm = np.asarray(p["samples_mm"], dtype=np.float64)
    if not len(mm):
        return None
    offsets = p.get("t")
    if offsets is not None and len(offsets) == len(mm):
        t = t0 + np.asarray(offsets, dtype=np.float64)
    else:
        t = t0 + np.arange(len(mm)) / fs
    return t, _Item(t, None, mm)


def build_timeline(
    raw: Sequence[Sequence[tuple[Sensor, dict[str, Any]]]],
) -> tuple[list[_Item], float]:
    """Tests laid end to end, LOOP_GAP_S apart; returns (items by last sample time, period s)."""
    items: list[_Item] = []
    cursor = 0.0
    for payloads in raw:
        parsed = [x for sensor, p in payloads if (x := _parse(sensor, p)) is not None]
        if not parsed:
            continue
        start = min(float(t[0]) for t, _ in parsed)
        end = max(float(t[-1]) for t, _ in parsed)
        for t, item in parsed:
            items.append(_Item(t - start + cursor, item.imu, item.mm))
        cursor += end - start + LOOP_GAP_S
    items.sort(key=lambda it: float(it.t[-1]))
    return items, cursor


class ReplaySource:
    name = "replay"

    def __init__(
        self,
        conn: sqlite3.Connection,
        test_ids: list[int],
        *,
        fast: bool = False,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.test_ids = list(test_ids)
        self._items, self._period = build_timeline(
            [queries.raw_for_test(conn, tid) for tid in self.test_ids]
        )
        if not self._items:
            raise ValueError(f"no raw samples to replay for tests {self.test_ids}")
        self._fast = fast
        self._clock = clock
        self._running = False
        self._base: float | None = None
        self._loop = 0
        self._next = 0
        self._status_sent = False
        self._imu_ts: deque[float] = deque(maxlen=RATE_HISTORY)
        self._tof_ts: deque[float] = deque(maxlen=RATE_HISTORY)

    async def start(self) -> None:
        self._running = True
        if self._base is None:
            self._base = self._clock()

    async def stop(self) -> None:
        self._running = False

    async def batches(self) -> AsyncIterator[Batch]:
        await self.start()
        if not self._status_sent:
            self._status_sent = True
            yield SourceStatus(connected=True, sensors=dict(SENSORS))
        while self._running:
            batch = self._shifted(self._items[self._next])
            if self._fast:
                await asyncio.sleep(0)  # let other tasks run between batches
            else:
                await asyncio.sleep(max(0.0, float(batch.t[-1]) - self._clock()))
            if not self._running:
                return
            self._advance()
            ts = self._imu_ts if isinstance(batch, ImuBatch) else self._tof_ts
            ts.extend(batch.t.tolist())
            yield batch

    async def led(self, command: LedCommand, value: int | None) -> None:
        return None

    def health(self) -> SourceHealth:
        return SourceHealth(
            connected=True,
            sensors_detected=dict(SENSORS),
            imu_hz=measured_rate(self._imu_ts),
            tof_hz=measured_rate(self._tof_ts),
        )

    def _shifted(self, item: _Item) -> ImuBatch | TofBatch:
        assert self._base is not None
        t = item.t + self._base + self._loop * self._period
        if item.imu is not None:
            return ImuBatch(t=t, acc=item.imu[:, :3], gyro=item.imu[:, 3:])
        assert item.mm is not None
        return TofBatch(t=t, mm=item.mm)

    def _advance(self) -> None:
        self._next += 1
        if self._next == len(self._items):
            self._next = 0
            self._loop += 1


def make_replay_source(config: Config) -> ReplaySource:
    """Replay config.replay_test_id, else the latest check with done rest, posture and reach."""
    conn = connect(config.db_path)
    try:
        if config.replay_test_id is not None:
            ids = [config.replay_test_id]
        else:
            ids = queries.latest_replayable_tests(conn)
        if not ids:
            raise ValueError(
                "nothing to replay: record a check with rest, posture and reach, or set"
                " REPLAY_TEST_ID"
            )
        return ReplaySource(conn, ids)
    finally:
        conn.close()
