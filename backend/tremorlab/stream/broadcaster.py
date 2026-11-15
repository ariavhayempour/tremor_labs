"""Consumes the sensor source: fills ring buffers, fans out messages, feeds the recorder."""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from tremorlab.sources.base import Batch, ImuBatch, SensorSource, SourceStatus, TofBatch
from tremorlab.stream.messages import Message, imu_msg, source_msg, tof_msg
from tremorlab.stream.ring import RingBuffer

IMU_RING_CAPACITY = 3000
TOF_RING_CAPACITY = 1500
MAX_QUEUE = 100
SOURCE_CHECK_S = 1.0
RATE_CHANGE_FRACTION = 0.05

log = logging.getLogger(__name__)


def _rate_moved(old: float | None, new: float | None) -> bool:
    if old is None or new is None:
        return old is not new
    return abs(new - old) > RATE_CHANGE_FRACTION * abs(old)


def source_changed(last: Message | None, new: Message) -> bool:
    """Link, sensors or source changed, or a measured rate moved > RATE_CHANGE_FRACTION."""
    if last is None:
        return True
    if any(last[k] != new[k] for k in ("sensor_source", "connected", "sensors")):
        return True
    return any(_rate_moved(last[k], new[k]) for k in ("imu_hz", "tof_hz"))


class Broadcaster:
    def __init__(
        self, source: SensorSource, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.source = source
        self._clock = clock
        self._last_source: Message | None = None
        self._source_checked = -float("inf")
        self.imu_ring = RingBuffer(IMU_RING_CAPACITY, 6)
        self.tof_ring = RingBuffer(TOF_RING_CAPACITY, 0)
        self._queues: list[asyncio.Queue[dict[str, Any]]] = []
        self._listener: Callable[[Batch], None] | None = None
        self._imu_fs: float | None = None
        self._tof_fs: float | None = None

    async def run(self) -> None:
        """Consume source.batches() until the source ends or the task is cancelled."""
        async for batch in self.source.batches():
            self.dispatch(batch)

    def dispatch(self, batch: Batch) -> None:
        if isinstance(batch, ImuBatch):
            if len(batch.t):
                self.imu_ring.append(batch.t, np.hstack([batch.acc, batch.gyro]))
                msg = imu_msg(batch, fallback_fs=self._imu_fs)
                if len(batch.t) >= 2:
                    self._imu_fs = msg["fs"]
                self.publish(msg)
        elif isinstance(batch, TofBatch):
            if len(batch.t):
                self.tof_ring.append(batch.t, batch.mm)
                msg = tof_msg(batch, fallback_fs=self._tof_fs)
                if len(msg["samples_mm"]) >= 2:
                    self._tof_fs = msg["fs"]
                if msg["samples_mm"]:
                    self.publish(msg)
        elif isinstance(batch, SourceStatus):
            self._publish_source()
        if self._clock() - self._source_checked >= SOURCE_CHECK_S:
            self._source_checked = self._clock()
            if source_changed(self._last_source, self.source_message()):
                self._publish_source()
        if self._listener is not None:
            try:
                self._listener(batch)
            except Exception:
                log.exception("stream listener failed")

    def source_message(self) -> Message:
        return source_msg(self.source.health(), self.source.name)

    def _publish_source(self) -> None:
        """Publish current health; also the reference that later changes are measured from."""
        self._last_source = self.source_message()
        self._source_checked = self._clock()
        self.publish(self._last_source)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        if q in self._queues:
            self._queues.remove(q)

    def publish(self, msg: dict[str, Any]) -> None:
        """Non-blocking fan-out; a queue over MAX_QUEUE loses its oldest messages."""
        for q in self._queues:
            q.put_nowait(msg)
            while q.qsize() > MAX_QUEUE:
                q.get_nowait()

    def set_listener(self, fn: Callable[[Batch], None] | None) -> None:
        self._listener = fn
