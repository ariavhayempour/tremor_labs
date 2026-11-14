import asyncio

import numpy as np

from tremorlab.config import SimParams
from tremorlab.sources.base import Batch, ImuBatch, SourceStatus, TofBatch
from tremorlab.sources.simulated import SimulatedSource
from tremorlab.stream.broadcaster import MAX_QUEUE, Broadcaster


def make() -> tuple[Broadcaster, SimulatedSource]:
    source = SimulatedSource(SimParams(), fast=True, seed=0)
    return Broadcaster(source), source


def imu(t0: float) -> ImuBatch:
    t = t0 + np.arange(10) / 100.0
    return ImuBatch(t=t, acc=np.zeros((10, 3)), gyro=np.zeros((10, 3)))


def test_dispatch_fills_rings_and_publishes() -> None:
    b, _ = make()
    q = b.subscribe()
    b.dispatch(imu(0.0))
    b.dispatch(TofBatch(t=np.arange(4) / 40.0, mm=np.array([200.0, np.nan, 201.0, 202.0])))
    assert len(b.imu_ring.window(10.0)[0]) == 10 and b.imu_ring.window(1.0)[1].shape[1] == 6
    assert len(b.tof_ring.window(10.0)[0]) == 4
    types = [q.get_nowait()["type"] for _ in range(q.qsize())]
    assert types == ["imu", "source", "tof"]  # first data also announces source health


def test_source_status_publishes_source_message() -> None:
    b, _ = make()
    q = b.subscribe()
    b.dispatch(SourceStatus(connected=True, sensors={"movement": True, "distance": True}))
    m = q.get_nowait()
    assert m["type"] == "source" and m["sensor_source"] == "sim" and m["connected"] is True


def test_source_message_republished_when_health_changes() -> None:
    now = [0.0]
    source = SimulatedSource(SimParams(), fast=True, seed=0)
    b = Broadcaster(source, clock=lambda: now[0])
    q = b.subscribe()

    async def feed(n_imu: int) -> None:
        await source.start()
        got = 0
        async for batch in source.batches():
            b.dispatch(batch)
            got += isinstance(batch, ImuBatch)
            if got == n_imu:
                return

    def drain_sources() -> list[dict[str, object]]:
        msgs = [q.get_nowait() for _ in range(q.qsize())]
        return [m for m in msgs if m["type"] == "source"]

    asyncio.run(feed(5))
    assert len(drain_sources()) == 1  # the initial SourceStatus; no re-check within a second
    now[0] = 1.0
    asyncio.run(feed(1))
    [fresh] = drain_sources()
    assert fresh["imu_hz"] is not None
    now[0] = 1.5
    asyncio.run(feed(1))
    assert drain_sources() == []


def test_publish_drops_oldest_beyond_limit() -> None:
    b, _ = make()
    q = b.subscribe()
    for i in range(MAX_QUEUE + 25):
        b.publish({"type": "x", "i": i})
    assert q.qsize() == MAX_QUEUE
    assert q.get_nowait()["i"] == 25


def test_unsubscribe_stops_delivery() -> None:
    b, _ = make()
    q = b.subscribe()
    b.unsubscribe(q)
    b.publish({"type": "x"})
    assert q.empty()
    b.unsubscribe(q)  # idempotent


def test_listener_receives_every_batch() -> None:
    b, _ = make()
    seen: list[Batch] = []
    b.set_listener(seen.append)
    b.dispatch(imu(0.0))
    b.set_listener(None)
    b.dispatch(imu(0.1))
    assert len(seen) == 1


def test_failing_listener_does_not_break_stream() -> None:
    b, _ = make()
    q = b.subscribe()

    def boom(_: Batch) -> None:
        raise RuntimeError("listener bug")

    b.set_listener(boom)
    b.dispatch(imu(0.0))
    assert q.get_nowait()["type"] == "imu"


def test_run_consumes_source_batches() -> None:
    async def go() -> int:
        b, source = make()
        await source.start()
        q = b.subscribe()
        task = asyncio.create_task(b.run())
        while q.qsize() < 10:
            await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return q.qsize()

    assert asyncio.run(go()) >= 10
