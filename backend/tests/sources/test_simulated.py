import asyncio
import dataclasses

import numpy as np
import pytest
from numpy.typing import NDArray
from scipy.signal import detrend

from tremorlab.config import SimParams
from tremorlab.sources.base import ImuBatch, SourceStatus, TofBatch
from tremorlab.sources.simulated import SimulatedSource

Arr = NDArray[np.float64]


async def _drain(source: SimulatedSource, seconds: float) -> tuple[Arr, Arr, Arr, Arr]:
    imu_t: list[Arr] = []
    acc: list[Arr] = []
    tof_t: list[Arr] = []
    mm: list[Arr] = []
    covered = 0.0
    async for b in source.batches():
        if isinstance(b, ImuBatch):
            imu_t.append(b.t)
            acc.append(b.acc)
            covered = float(b.t[-1] - imu_t[0][0])
        elif isinstance(b, TofBatch):
            tof_t.append(b.t)
            mm.append(b.mm)
        if covered >= seconds - 0.011 and len(tof_t) == len(imu_t):
            break
    return np.concatenate(imu_t), np.vstack(acc), np.concatenate(tof_t), np.concatenate(mm)


def collect(source: SimulatedSource, seconds: float) -> tuple[Arr, Arr, Arr, Arr]:
    """Drain fast-mode batches covering `seconds` of signal: (imu_t, acc, tof_t, mm)."""
    return asyncio.run(_drain(source, seconds))


def fast(params: SimParams | None = None, seed: int = 1) -> SimulatedSource:
    return SimulatedSource(params or SimParams(), fast=True, seed=seed)


def started(params: SimParams | None = None, seed: int = 1) -> SimulatedSource:
    source = fast(params, seed)
    asyncio.run(source.start())
    return source


def effective_rate(t: Arr) -> float:
    return float(np.median(1.0 / np.diff(t)))


def peak_freq(t: Arr, x: Arr) -> float:
    fs = effective_rate(t)
    spec = np.abs(np.fft.rfft(detrend(x)))
    freqs = np.fft.rfftfreq(len(x), 1.0 / fs)
    above_drift = freqs > 1.0
    return float(freqs[above_drift][np.argmax(spec[above_drift])])


def test_imu_rate_is_100hz() -> None:
    imu_t, _, _, _ = collect(started(), 5.0)
    assert abs(effective_rate(imu_t) - 100.0) < 0.5


def test_tof_rate_is_40hz() -> None:
    _, _, tof_t, _ = collect(started(), 5.0)
    assert abs(effective_rate(tof_t) - 40.0) < 0.5


def test_batches_are_100ms_with_10_imu_and_4_tof_samples() -> None:
    async def first_batches() -> list[ImuBatch | TofBatch]:
        source = fast()
        await source.start()
        out: list[ImuBatch | TofBatch] = []
        async for b in source.batches():
            if isinstance(b, ImuBatch | TofBatch):
                out.append(b)
            if len(out) == 4:
                break
        return out

    imu1, tof1, imu2, tof2 = asyncio.run(first_batches())
    assert isinstance(imu1, ImuBatch) and isinstance(imu2, ImuBatch)
    assert isinstance(tof1, TofBatch) and isinstance(tof2, TofBatch)
    assert imu1.acc.shape == (10, 3) and imu1.gyro.shape == (10, 3) and tof1.mm.shape == (4,)
    assert imu2.t[0] - imu1.t[0] == pytest.approx(0.1)


def test_first_batch_is_connected_status() -> None:
    async def first() -> object:
        source = fast()
        await source.start()
        async for b in source.batches():
            return b
        return None

    b = asyncio.run(first())
    assert isinstance(b, SourceStatus) and b.connected
    assert b.sensors == {"movement": True, "distance": True}


def test_gravity_on_z() -> None:
    _, acc, _, _ = collect(started(), 10.0)
    assert abs(acc[:, 2].mean() - 9.81) < 0.05


def test_tremor_frequency_dominates() -> None:
    imu_t, acc, _, _ = collect(started(SimParams(tremor_hz=6.0)), 10.0)
    assert abs(peak_freq(imu_t, acc[:, 0]) - 6.0) <= 0.1


def test_set_params_changes_frequency() -> None:
    source = started(SimParams(tremor_hz=5.0))
    t1, a1, _, _ = collect(source, 5.0)
    assert source.set_params(tremor_hz=8.0).tremor_hz == 8.0
    t2, a2, _, _ = collect(source, 5.0)
    assert abs(peak_freq(t1, a1[:, 0]) - 5.0) <= 0.2
    assert abs(peak_freq(t2, a2[:, 0]) - 8.0) <= 0.2
    assert t2[0] > t1[-1]


def test_set_params_rejects_unknown_field() -> None:
    with pytest.raises(ValueError):
        started().set_params(volume=3.0)


def test_tof_mean_matches_hand_height() -> None:
    _, _, _, mm = collect(started(), 5.0)
    assert abs(mm.mean() - 200) < 5


def test_descent_goes_from_300_to_below_40_within_3s() -> None:
    source = started()
    collect(source, 1.0)
    source.trigger_descent()
    _, _, tof_t, mm = collect(source, 3.0)
    assert abs(mm[0] - 300) < 5
    assert mm.min() < 40
    assert tof_t[int(np.argmin(mm))] - tof_t[0] <= 3.0


def test_descent_wobble_only_in_final_50mm() -> None:
    def descent(wobble: float) -> Arr:
        source = started(SimParams(reach_wobble=wobble), seed=3)
        collect(source, 0.5)
        source.trigger_descent()
        return collect(source, 2.5)[3]

    smooth, wobbly = descent(0.0), descent(6.0)
    differs = np.abs(wobbly - smooth) > 1e-9
    assert not differs[smooth > 30 + 50 + 5].any()
    assert differs[smooth < 30 + 50 - 5].any()


def test_seed_makes_output_deterministic() -> None:
    _, a1, _, m1 = collect(started(seed=7), 2.0)
    _, a2, _, m2 = collect(started(seed=7), 2.0)
    _, a3, _, _ = collect(started(seed=8), 2.0)
    assert np.array_equal(a1, a2) and np.array_equal(m1, m2)
    assert not np.array_equal(a1, a3)


def test_params_property_and_health() -> None:
    source = started(SimParams(hand_mm=150.0))
    assert source.params == dataclasses.replace(SimParams(), hand_mm=150.0)
    assert source.health().imu_hz is None
    collect(source, 2.0)
    health = source.health()
    assert health.connected and health.sensors_detected == {"movement": True, "distance": True}
    assert health.imu_hz is not None and abs(health.imu_hz - 100.0) < 1.0
    assert health.tof_hz is not None and abs(health.tof_hz - 40.0) < 1.0


def test_stop_ends_the_batch_stream() -> None:
    async def run() -> int:
        source = fast()
        await source.start()
        n = 0
        async for _ in source.batches():
            n += 1
            if n == 5:
                await source.stop()
        return n

    assert asyncio.run(run()) == 5


def test_real_time_mode_paces_batches() -> None:
    async def run() -> float:
        source = SimulatedSource(SimParams(), seed=0)
        await source.start()
        loop = asyncio.get_running_loop()
        began = loop.time()
        imu = 0
        async for b in source.batches():
            imu += isinstance(b, ImuBatch)
            if imu == 3:
                break
        await source.stop()
        return loop.time() - began

    assert 0.25 <= asyncio.run(run()) < 0.6
