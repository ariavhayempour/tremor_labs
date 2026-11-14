import asyncio
import json
import socket
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import numpy as np
import pytest

from tremorlab.sources import board
from tremorlab.sources.base import Batch, ImuBatch, SourceStatus, TofBatch
from tremorlab.sources.board import (
    BoardSource,
    MicrosUnwrapper,
    decode_imu,
    decode_tof,
    parse_line,
)

FIXTURE = Path(__file__).parent / "fixtures" / "board_stream.ndjson"
WAIT_S = 3.0
FAKE_NOW = 1000.0

Conn = tuple[asyncio.StreamReader, asyncio.StreamWriter]


@pytest.fixture(autouse=True)
def fast_timing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink link timeouts and backoff so real-time waits stay short."""
    monkeypatch.setattr(board, "STALE_TIMEOUT_S", 0.3)
    monkeypatch.setattr(board, "RECONNECT_STALE_S", 0.8)
    monkeypatch.setattr(board, "BACKOFF_INITIAL_S", 0.05)
    monkeypatch.setattr(board, "BACKOFF_MAX_S", 0.2)


class FakeRelay:
    """TCP server on port 0 that hands each accepted connection to the test."""

    def __init__(self) -> None:
        self.conns: asyncio.Queue[Conn] = asyncio.Queue()
        self._done = asyncio.Event()
        self.port = 0
        self._server: asyncio.Server | None = None

    async def __aenter__(self) -> "FakeRelay":
        self._server = await asyncio.start_server(self._on_conn, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._done.set()
        assert self._server is not None
        self._server.close()
        await self._server.wait_closed()

    async def _on_conn(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await self.conns.put((reader, writer))
        await self._done.wait()
        writer.close()

    async def accept(self) -> Conn:
        return await asyncio.wait_for(self.conns.get(), WAIT_S)


def imu_line(t_us: list[int], mg: int = 0, mdps: int = 0) -> bytes:
    d: list[int] = []
    for t in t_us:
        d += [t, mg, 0, 1000, mdps, 0, 0]
    return json.dumps({"k": "imu", "d": d}).encode() + b"\n"


def tof_line(t_us: list[int], mm: int = 200) -> bytes:
    d: list[int] = []
    for t in t_us:
        d += [t, mm]
    return json.dumps({"k": "tof", "d": d}).encode() + b"\n"


def status_line(state: str) -> bytes:
    return json.dumps({"k": "status", "d": [state, 100, 40, 0]}).encode() + b"\n"


async def next_matching(
    it: AsyncIterator[Batch], pred: Callable[[Batch], bool], timeout: float = WAIT_S
) -> Batch:
    async def scan() -> Batch:
        async for b in it:
            if pred(b):
                return b
        raise AssertionError("batch stream ended")

    return await asyncio.wait_for(scan(), timeout)


async def collect_imu_sizes(
    it: AsyncIterator[Batch], n: int, timeout: float = WAIT_S
) -> tuple[np.ndarray, list[int]]:
    """Gather IMU batches until n samples arrive; checks strict ordering across batches."""
    ts: list[np.ndarray] = []
    sizes: list[int] = []
    while sum(sizes) < n:
        b = await next_matching(it, is_imu, timeout)
        assert isinstance(b, ImuBatch)
        ts.append(b.t)
        sizes.append(b.t.size)
    t = np.concatenate(ts)
    assert t.size == n
    assert np.all(np.diff(t) > 0)
    return t, sizes


async def collect_imu(
    it: AsyncIterator[Batch], n: int, timeout: float = WAIT_S
) -> tuple[np.ndarray, np.ndarray]:
    """Gather n IMU samples in order; returns (t, acc)."""
    ts: list[np.ndarray] = []
    accs: list[np.ndarray] = []
    while sum(x.size for x in ts) < n:
        b = await next_matching(it, is_imu, timeout)
        assert isinstance(b, ImuBatch)
        ts.append(b.t)
        accs.append(b.acc)
    t = np.concatenate(ts)
    assert t.size == n
    assert np.all(np.diff(t) > 0)
    return t, np.concatenate(accs)


def is_imu(b: Batch) -> bool:
    return isinstance(b, ImuBatch)


def is_tof(b: Batch) -> bool:
    return isinstance(b, TofBatch)


def link(connected: bool) -> Callable[[Batch], bool]:
    return lambda b: isinstance(b, SourceStatus) and b.connected is connected and not b.sensors


def sensors_status(b: Batch) -> bool:
    return isinstance(b, SourceStatus) and bool(b.sensors)


def run_with_source(
    body: Callable[[BoardSource, FakeRelay, AsyncIterator[Batch]], Awaitable[None]],
) -> None:
    async def main() -> None:
        async with FakeRelay() as relay:
            src = BoardSource("127.0.0.1", relay.port, clock=lambda: FAKE_NOW)
            await src.start()
            try:
                await body(src, relay, aiter(src.batches()))
            finally:
                await src.stop()

    asyncio.run(main())


# Pure helpers


def test_parse_line_rejects_garbage() -> None:
    garbage = [b"", b"\n", b"not json\n", b"[1, 2]\n", b'{"d": [1]}\n', b'{"k": 5}\n', b"\xff\xfe"]
    for bad in garbage:
        assert parse_line(bad) is None
    assert parse_line(b'{"k":"imu","d":[1]}\n') == {"k": "imu", "d": [1]}


def test_decode_imu_units() -> None:
    t_us, acc, gyro = decode_imu([100, 1000, 0, -1000, 1000, 0, -500])
    assert t_us.tolist() == [100]
    assert acc.shape == (1, 3) and gyro.shape == (1, 3)
    np.testing.assert_allclose(acc[0], [9.80665, 0.0, -9.80665])
    np.testing.assert_allclose(gyro[0], [1.0, 0.0, -0.5])


def test_decode_tof_mm_as_float() -> None:
    t_us, mm = decode_tof([10, 200, 30, 215])
    assert t_us.tolist() == [10, 30]
    assert mm.dtype == np.float64
    assert mm.tolist() == [200.0, 215.0]


def test_decode_rejects_bad_length_and_types() -> None:
    with pytest.raises(ValueError):
        decode_imu([1, 2, 3, 4, 5, 6, 7, 8])
    with pytest.raises(ValueError):
        decode_tof([1, 2, 3])
    with pytest.raises(ValueError):
        decode_tof([1, "200"])  # type: ignore[list-item]
    with pytest.raises(ValueError):
        decode_tof([1, 2.5])  # type: ignore[list-item]


def test_decode_normalizes_signed_t_us() -> None:
    t_us, _ = decode_tof([2147483000, 1, -2147483000, 1, -2147482000, 1])
    assert t_us.tolist() == [2147483000, 2147484296, 2147485296]
    s = MicrosUnwrapper()(t_us)
    assert np.all(np.diff(s) > 0)
    assert s[-1] - s[0] == pytest.approx(2296e-6)


def test_unwrapper_handles_rollover() -> None:
    s = MicrosUnwrapper()(np.array([4294967000, 4294967290, 200, 500], dtype=np.int64))
    assert np.all(np.diff(s) > 0)
    np.testing.assert_allclose(s, [0.0, 290e-6, 496e-6, 796e-6])


def test_unwrapper_handles_rollover_between_batches() -> None:
    unwrap = MicrosUnwrapper()
    a = unwrap(np.array([4294967000, 4294967290], dtype=np.int64))
    b = unwrap(np.array([200, 500], dtype=np.int64))
    s = np.concatenate([a, b])
    assert np.all(np.diff(s) > 0)
    np.testing.assert_allclose(b, [496e-6, 796e-6])


# Link behavior against a fake relay


def test_burst_delivery_uses_mcu_timestamps() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        # Three 100 ms batches delivered late in a single chunk.
        w.write(
            b"".join(
                imu_line([1_000_000 + 10_000 * i for i in range(10 * k, 10 * k + 10)])
                for k in range(3)
            )
        )
        await w.drain()
        t, _ = await collect_imu(it, 30)
        np.testing.assert_allclose(np.diff(t), 0.01, atol=1e-9)
        assert t[9] == pytest.approx(FAKE_NOW)

    run_with_source(body)


def test_late_sample_is_emitted_in_order() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        order = [0, 1, 2, 4, 3, 5, 6, 7]  # sample 3 arrives one position late
        w.write(b"".join(imu_line([1_000_000 + 10_000 * i], mg=i) for i in order))
        await w.drain()
        t, acc = await collect_imu(it, 8)
        np.testing.assert_allclose(np.diff(t), 0.01, atol=1e-9)
        np.testing.assert_allclose(acc[:, 0], np.arange(8) * board.MG_TO_M_S2)

    run_with_source(body)


def test_duplicate_or_too_late_sample_is_dropped() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        w.write(b"".join(imu_line([1_000_000 + 10_000 * i]) for i in range(5)))
        await w.drain()
        first, _ = await collect_imu(it, 5)
        # A repeat of an emitted sample and one older than everything emitted.
        w.write(imu_line([1_040_000]) + imu_line([1_005_000]) + imu_line([1_050_000]))
        await w.drain()
        second, _ = await collect_imu(it, 1)
        assert second[0] - first[-1] == pytest.approx(0.01)

    run_with_source(body)


def test_batches_group_samples_per_sample_lines() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        for k in range(30):  # 300 ms of one-sample lines, paced at 10 ms
            w.write(imu_line([1_000_000 + 10_000 * k]))
            await w.drain()
            await asyncio.sleep(0.01)
        _, sizes = await collect_imu_sizes(it, 30)
        assert len(sizes) < 15
        assert max(sizes) > 1

    run_with_source(body)


def test_imu_and_tof_share_clock_mapping() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        w.write(imu_line([1_000_000, 1_010_000]) + tof_line([1_050_000, 1_075_000], mm=180))
        await w.drain()
        imu = await next_matching(it, is_imu)
        tof = await next_matching(it, is_tof)
        assert isinstance(imu, ImuBatch) and isinstance(tof, TofBatch)
        assert tof.t[0] - imu.t[0] == pytest.approx(0.05)
        assert tof.mm.tolist() == [180.0, 180.0]

    run_with_source(body)


def test_malformed_lines_are_skipped() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        w.write(b"garbage\n" + b'{"k":"imu","d":[1,2,3]}\n' + b'{"k":"tof","d":"x"}\n')
        w.write(b'{"k":"what","d":[]}\n' + imu_line([5_000, 15_000]))
        await w.drain()
        imu = await next_matching(it, is_imu)
        assert isinstance(imu, ImuBatch)
        assert imu.t.size == 2

    run_with_source(body)


def test_disconnect_sets_health_false_then_reconnects() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        assert src.health().connected is False
        _, w = await relay.accept()
        w.write(imu_line([1_000, 11_000]))
        await w.drain()
        await next_matching(it, link(True))
        assert src.health().connected is True

        w.close()
        await next_matching(it, link(False))
        assert src.health().connected is False

        _, w2 = await relay.accept()
        w2.write(imu_line([500_000, 510_000]))
        await w2.drain()
        await next_matching(it, link(True))
        assert src.health().connected is True

    run_with_source(body)


def test_silent_link_reports_disconnected() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        w.write(imu_line([1_000, 11_000]))
        await w.drain()
        await next_matching(it, link(True))
        silent = await next_matching(it, link(False))
        assert isinstance(silent, SourceStatus)
        assert src.health().connected is False
        assert src.health().imu_hz is None
        # Long silence forces a fresh connection.
        await relay.accept()

    run_with_source(body)


def test_start_without_board_does_not_fail() -> None:
    async def main() -> None:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        src = BoardSource("127.0.0.1", port)
        await src.start()
        await asyncio.sleep(0.3)
        h = src.health()
        assert h.connected is False
        assert h.imu_hz is None and h.tof_hz is None
        await src.led("countdown", 3)
        await src.stop()

    asyncio.run(main())


def test_led_writes_json_line() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        r, _ = await relay.accept()
        await src.led("countdown", 7)
        await src.led("clear", None)
        first = await asyncio.wait_for(r.readline(), WAIT_S)
        second = await asyncio.wait_for(r.readline(), WAIT_S)
        assert first == b'{"k":"led","cmd":"countdown","value":7}\n'
        assert second == b'{"k":"led","cmd":"clear","value":0}\n'

    run_with_source(body)


def test_status_missing_sensor_reported() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        w.write(status_line("ok"))
        await w.drain()
        ok = await next_matching(it, sensors_status)
        assert isinstance(ok, SourceStatus)
        assert ok.sensors == {"movement": True, "distance": True}

        w.write(status_line("ok") + status_line("distance_missing"))
        await w.drain()
        missing = await next_matching(it, sensors_status)
        assert isinstance(missing, SourceStatus)
        assert missing.connected is True
        assert missing.sensors == {"movement": True, "distance": False}
        assert src.health().sensors_detected == {"movement": True, "distance": False}

        w.write(status_line("movement_missing"))
        await w.drain()
        moved = await next_matching(it, sensors_status)
        assert isinstance(moved, SourceStatus)
        assert moved.sensors == {"movement": False, "distance": True}

    run_with_source(body)


def test_status_both_missing() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        w.write(status_line("both_missing"))
        await w.drain()
        st = await next_matching(it, sensors_status)
        assert isinstance(st, SourceStatus)
        assert st.sensors == {"movement": False, "distance": False}
        h = src.health()
        assert h.connected is True
        assert h.sensors_detected == {"movement": False, "distance": False}

    run_with_source(body)


def test_health_rates_measured_from_timestamps() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        imu_t = [10_000 * i for i in range(300)]  # 3 s at 100 Hz
        tof_t = [25_000 * i + (5_000 if i % 3 == 0 else 0) for i in range(120)]  # uneven, ~40 Hz
        w.write(b"".join(imu_line(imu_t[i : i + 10]) for i in range(0, 300, 10)))
        w.write(tof_line(tof_t))
        await w.drain()
        n_tof = 0
        while n_tof < 120:
            b = await next_matching(it, is_tof)
            assert isinstance(b, TofBatch)
            n_tof += b.t.size
        h = src.health()
        assert h.imu_hz == pytest.approx(100.0, rel=0.02)
        assert h.tof_hz == pytest.approx(40.0, rel=0.05)

    run_with_source(body)


@pytest.mark.skipif(not FIXTURE.exists(), reason="board capture not recorded yet")
def test_fixture_stream_rate_near_100hz() -> None:
    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        w.write(FIXTURE.read_bytes())
        await w.drain()
        ts: list[np.ndarray] = []
        try:
            while True:
                b = await next_matching(it, is_imu, timeout=0.5)
                if isinstance(b, ImuBatch):
                    ts.append(b.t)
        except TimeoutError:
            pass
        t = np.concatenate(ts)
        assert t.size > 100
        assert float(np.median(1 / np.diff(t))) == pytest.approx(100.0, abs=5.0)

    run_with_source(body)


@pytest.mark.skipif(not FIXTURE.exists(), reason="board capture not recorded yet")
def test_fixture_has_no_lost_samples_after_reorder() -> None:
    n_imu = sum(1 for line in FIXTURE.read_bytes().splitlines() if b'"k":"imu"' in line)

    async def body(src: BoardSource, relay: FakeRelay, it: AsyncIterator[Batch]) -> None:
        _, w = await relay.accept()
        w.write(FIXTURE.read_bytes())
        await w.drain()
        t, _ = await collect_imu(it, n_imu)
        assert float(np.median(1 / np.diff(t))) == pytest.approx(100.0, abs=5.0)

    assert n_imu > 100
    run_with_source(body)
