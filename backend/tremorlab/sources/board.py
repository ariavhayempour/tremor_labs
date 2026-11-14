"""BoardSource: NDJSON TCP client for the UNO Q relay (wire protocol in docs/contracts.md)."""

import asyncio
import contextlib
import json
import logging
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray

from tremorlab.sources.base import (
    Batch,
    ImuBatch,
    LedCommand,
    SourceHealth,
    SourceStatus,
    TofBatch,
)

log = logging.getLogger(__name__)

# Link timing (seconds); read at call time so tests can shrink them.
STALE_TIMEOUT_S = 1.0
RECONNECT_STALE_S = 5.0
BACKOFF_INITIAL_S = 0.5
BACKOFF_MAX_S = 5.0
CONNECT_TIMEOUT_S = 2.0
LED_WRITE_TIMEOUT_S = 1.0
RATE_WINDOW_S = 5.0
REORDER_HOLD_S = 0.05  # MCU-time hold so lines delivered out of order can be sorted
REORDER_IDLE_FLUSH_S = 0.1  # loop-time quiet after which a stream releases everything held
EMIT_INTERVAL_S = 0.05

READ_LIMIT_BYTES = 1 << 20
QUEUE_MAXSIZE = 1000

STANDARD_GRAVITY_M_S2 = 9.80665
MG_TO_M_S2 = STANDARD_GRAVITY_M_S2 / 1000.0
MDPS_TO_DPS = 1.0 / 1000.0
IMU_STRIDE = 7
TOF_STRIDE = 2

MICROS_WRAP = 1 << 32
MICROS_HALF = 1 << 31
MICROS_MASK = MICROS_WRAP - 1
MICROS_MIN = -MICROS_HALF  # the Bridge carries int32, so t_us >= 2^31 arrives negative
US_PER_S = 1_000_000.0

STATUS_SENSORS: dict[str, dict[str, bool]] = {
    "ok": {"movement": True, "distance": True},
    "movement_missing": {"movement": False, "distance": True},
    "distance_missing": {"movement": True, "distance": False},
    "both_missing": {"movement": False, "distance": False},
}


def parse_line(line: bytes) -> dict[str, Any] | None:
    """Decode one NDJSON line; None for malformed input."""
    try:
        msg = json.loads(line)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(msg, dict) or not isinstance(msg.get("k"), str):
        return None
    return msg


class MicrosUnwrapper:
    """Turns 32-bit micros() values into seconds since the first sample, across 2³² rollover."""

    def __init__(self) -> None:
        self._last_raw: int | None = None
        self._last_abs_us = 0

    def __call__(self, t_us: NDArray[np.int64]) -> NDArray[np.float64]:
        raw = np.asarray(t_us, dtype=np.int64) & MICROS_MASK
        if raw.size == 0:
            return np.empty(0, dtype=np.float64)
        if self._last_raw is None:
            self._last_raw = int(raw[0])
        prev = np.concatenate([[self._last_raw], raw[:-1]])
        # Shortest signed step mod 2^32: a slightly older sample from the other stream is no wrap.
        step = ((raw - prev + MICROS_HALF) % MICROS_WRAP) - MICROS_HALF
        abs_us = self._last_abs_us + np.cumsum(step)
        self._last_raw = int(raw[-1])
        self._last_abs_us = int(abs_us[-1])
        return abs_us.astype(np.float64) / US_PER_S


def _flat_ints(d: list[int], stride: int) -> NDArray[np.int64]:
    """Validate a flat int list of whole samples and reshape to (N, stride), t_us made unsigned."""
    if len(d) % stride != 0:
        raise ValueError(f"length {len(d)} is not a multiple of {stride}")
    if any(type(x) is not int for x in d):
        raise ValueError("non-integer value")
    try:
        arr = np.asarray(d, dtype=np.int64).reshape(-1, stride)
    except OverflowError as e:
        raise ValueError("integer out of range") from e
    t = arr[:, 0]
    if np.any(t < MICROS_MIN) or np.any(t > MICROS_MASK):
        raise ValueError("t_us outside 32 bits")
    arr[:, 0] = t & MICROS_MASK
    return arr


def decode_imu(d: list[int]) -> tuple[NDArray[np.int64], NDArray[np.float64], NDArray[np.float64]]:
    """Flat [t_us, ax_mg, ay_mg, az_mg, gx_mdps, gy_mdps, gz_mdps, ...] → (t_us, m/s², deg/s)."""
    arr = _flat_ints(d, IMU_STRIDE)
    acc = arr[:, 1:4].astype(np.float64) * MG_TO_M_S2
    gyro = arr[:, 4:7].astype(np.float64) * MDPS_TO_DPS
    return arr[:, 0].copy(), acc, gyro


def decode_tof(d: list[int]) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
    """Flat [t_us, mm, ...] → (t_us, mm)."""
    arr = _flat_ints(d, TOF_STRIDE)
    return arr[:, 0].copy(), arr[:, 1].astype(np.float64)


def _rate_hz(times: deque[float], newest_s: float) -> float | None:
    """Mean rate in Hz of sample times (s) inside the window ending at newest_s."""
    while times and times[0] < newest_s - RATE_WINDOW_S:
        times.popleft()
    if len(times) < 2 or times[-1] <= times[0]:
        return None
    return (len(times) - 1) / (times[-1] - times[0])


class _ReorderStream:
    """Holds one stream's samples (MCU s, value rows) until they can be emitted in MCU order."""

    def __init__(self, name: str, width: int) -> None:
        self.name = name
        self._width = width
        self._s: list[NDArray[np.float64]] = []
        self._rows: list[NDArray[np.float64]] = []
        self._newest_s = -np.inf
        self._last_arrival = -np.inf
        self.last_emitted_s = -np.inf
        self.times: deque[float] = deque()

    def add(self, s: NDArray[np.float64], rows: NDArray[np.float64], now: float) -> None:
        """Queue samples at MCU s (s); now is loop time (s) of arrival."""
        if s.size == 0:
            return
        self._s.append(s)
        self._rows.append(rows.reshape(-1, self._width))
        self._newest_s = max(self._newest_s, float(s.max()))
        self._last_arrival = now

    def release(
        self, now: float, *, force: bool
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]] | None:
        """Pop samples older than the hold (all when forced or idle), sorted, duplicates dropped."""
        if not self._s:
            return None
        s = np.concatenate(self._s)
        rows = np.vstack(self._rows)
        if force or now - self._last_arrival >= REORDER_IDLE_FLUSH_S:
            ready = np.ones(s.size, dtype=np.bool_)
        else:
            ready = s <= self._newest_s - REORDER_HOLD_S
        self._s = [s[~ready]] if not ready.all() else []
        self._rows = [rows[~ready]] if self._s else []
        if not ready.any():
            return None
        order = np.argsort(s[ready], kind="stable")
        s, rows = s[ready][order], rows[ready][order]
        floor = np.maximum.accumulate(np.concatenate([[self.last_emitted_s], s]))[:-1]
        fresh = s > floor
        if not fresh.all():
            log.warning("%d duplicate or late %s samples dropped", int((~fresh).sum()), self.name)
        s, rows = s[fresh], rows[fresh]
        if s.size == 0:
            return None
        self.last_emitted_s = float(s[-1])
        self.times.extend(s.tolist())
        return s, rows


class BoardSource:
    name = "board"

    def __init__(self, host: str, port: int, *, clock: Callable[[], float] = time.time) -> None:
        self._host = host
        self._port = port
        self._clock = clock
        self._queue: asyncio.Queue[Batch | None] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._task: asyncio.Task[None] | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._sensors: dict[str, bool] = {}
        self._reset_stream_state()

    def _reset_stream_state(self) -> None:
        """Per-connection MCU clock state; a reconnect may follow a board restart."""
        self._unwrap = MicrosUnwrapper()
        self._anchor: tuple[float, float] | None = None
        self._imu = _ReorderStream("imu", 6)
        self._tof = _ReorderStream("tof", 1)

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="board-source")

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._close_writer()
        self._connected = False
        self._sensors = {}
        self._emit(None)

    def batches(self) -> AsyncIterator[Batch]:
        return self._iter_batches()

    async def _iter_batches(self) -> AsyncIterator[Batch]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    async def led(self, command: LedCommand, value: int | None) -> None:
        writer = self._writer
        if writer is None or writer.is_closing():
            return
        msg = {"k": "led", "cmd": command, "value": 0 if value is None else int(value)}
        try:
            writer.write(json.dumps(msg, separators=(",", ":")).encode() + b"\n")
            await asyncio.wait_for(writer.drain(), LED_WRITE_TIMEOUT_S)
        except (OSError, TimeoutError, RuntimeError) as e:
            log.warning("led write failed: %s", e)

    def health(self) -> SourceHealth:
        if not self._connected:
            return SourceHealth(False, dict(self._sensors), None, None)
        newest = max(self._imu.last_emitted_s, self._tof.last_emitted_s)
        return SourceHealth(
            connected=True,
            sensors_detected=dict(self._sensors),
            imu_hz=_rate_hz(self._imu.times, newest),
            tof_hz=_rate_hz(self._tof.times, newest),
        )

    def _emit(self, item: Batch | None) -> None:
        """Enqueue without blocking; drops the oldest item when no consumer keeps up."""
        if self._queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
        self._queue.put_nowait(item)

    def _close_writer(self) -> None:
        writer, self._writer = self._writer, None
        if writer is not None:
            with contextlib.suppress(Exception):
                writer.close()

    async def _run(self) -> None:
        backoff = BACKOFF_INITIAL_S
        while True:
            got_data = False
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port, limit=READ_LIMIT_BYTES),
                    CONNECT_TIMEOUT_S,
                )
            except (OSError, TimeoutError) as e:
                log.debug("board connect failed: %s", e)
            else:
                self._writer = writer
                self._reset_stream_state()
                reason = "connection closed"
                try:
                    got_data, reason = await self._read_loop(reader)
                finally:
                    self._close_writer()
                    self._mark_disconnected(reason)
            # A connect that yields no data (e.g. adb forward with no relay) still backs off.
            if got_data:
                backoff = BACKOFF_INITIAL_S
            await asyncio.sleep(backoff)
            if not got_data:
                backoff = min(backoff * 2, BACKOFF_MAX_S)

    async def _read_loop(self, reader: asyncio.StreamReader) -> tuple[bool, str]:
        """Read lines until EOF, error or long silence; returns (got any data, reason)."""
        loop = asyncio.get_running_loop()
        last_data = last_flush = loop.time()
        got_data = False
        while True:
            line: bytes | None = None
            try:
                line = await asyncio.wait_for(reader.readline(), EMIT_INTERVAL_S)
            except TimeoutError:
                pass
            except ValueError:
                log.warning("board line over %d bytes skipped", READ_LIMIT_BYTES)
            except OSError as e:
                return got_data, f"connection error: {e}"
            if line == b"":
                return got_data, "connection closed"
            now = loop.time()
            if line is not None and self._handle_line(line, now):
                last_data = now
                got_data = True
            if now - last_flush >= EMIT_INTERVAL_S:
                self._flush(now, force=False)
                last_flush = now
            silent = now - last_data
            if self._connected and silent >= STALE_TIMEOUT_S:
                self._mark_disconnected("no data")
            if silent >= RECONNECT_STALE_S:
                return got_data, "no data"

    def _mark_connected(self) -> None:
        self._connected = True
        self._emit(SourceStatus(connected=True, sensors=dict(self._sensors), message="connected"))

    def _mark_disconnected(self, reason: str) -> None:
        if not self._connected:
            return
        self._flush(0.0, force=True)
        self._connected = False
        self._sensors = {}
        self._imu.times.clear()
        self._tof.times.clear()
        self._emit(SourceStatus(connected=False, message=reason))

    def _ensure_connected(self) -> None:
        if not self._connected:
            self._mark_connected()

    def _flush(self, now: float, *, force: bool) -> None:
        """Emit whatever each stream's reorder window releases as one batch per stream."""
        if self._anchor is None:
            return
        mac0, mcu0 = self._anchor
        imu = self._imu.release(now, force=force)
        if imu is not None:
            s, rows = imu
            self._emit(ImuBatch(t=mac0 + (s - mcu0), acc=rows[:, :3], gyro=rows[:, 3:]))
        tof = self._tof.release(now, force=force)
        if tof is not None:
            s, rows = tof
            self._emit(TofBatch(t=mac0 + (s - mcu0), mm=rows[:, 0]))

    def _handle_line(self, line: bytes, now: float) -> bool:
        """Apply one wire line received at loop time now (s); True when it was a valid message."""
        msg = parse_line(line)
        if msg is None:
            log.warning("malformed board line skipped: %r", line[:80])
            return False
        kind, d = msg["k"], msg.get("d")
        if kind not in ("imu", "tof", "status") or not isinstance(d, list):
            log.warning("unexpected board message skipped: %r", line[:80])
            return False
        try:
            if kind == "imu":
                t_us, acc, gyro = decode_imu(d)
                self._ensure_connected()
                self._imu.add(self._to_mcu_s(t_us), np.hstack([acc, gyro]), now)
            elif kind == "tof":
                t_us, mm = decode_tof(d)
                self._ensure_connected()
                self._tof.add(self._to_mcu_s(t_us), mm, now)
            else:
                self._handle_status(d)
        except ValueError as e:
            log.warning("bad %s message skipped: %s", kind, e)
            return False
        return True

    def _handle_status(self, d: list[Any]) -> None:
        state = d[0] if d else None
        if not isinstance(state, str) or state not in STATUS_SENSORS:
            raise ValueError(f"unknown status {state!r}")
        self._ensure_connected()
        sensors = STATUS_SENSORS[state]
        if sensors != self._sensors:
            self._sensors = dict(sensors)
            self._emit(SourceStatus(connected=True, sensors=dict(sensors), message=state))

    def _to_mcu_s(self, t_us: NDArray[np.int64]) -> NDArray[np.float64]:
        """Unwrap micros to MCU s on the shared clock, anchoring it on the first message."""
        s = self._unwrap(t_us)
        if self._anchor is None and s.size:
            # Anchor on the newest sample of the first message: it was sent just before arrival.
            self._anchor = (self._clock(), float(s.max()))
        return s
