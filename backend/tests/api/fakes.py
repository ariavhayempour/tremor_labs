"""Shared test doubles for session and API tests: fake analyzers, clock and a silent source."""

import asyncio
import dataclasses
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from tremorlab.analysis import Analyzers
from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.reach import ReachResult
from tremorlab.analysis.tap import TapResult
from tremorlab.analysis.tremor import TremorResult
from tremorlab.config import SimParams
from tremorlab.sources.base import Batch, ImuBatch, LedCommand, SourceHealth, TofBatch
from tremorlab.sources.simulated import SimulatedSource

DATA_T0 = 1_800_000_000.0
FREQS = np.arange(0.0, 50.25, 0.25)
FIXED = TremorResult(
    peak_hz=5.0,
    strength_ms2=0.2,
    strength_score=50.0,
    tremor_detected=True,
    freqs=FREQS,
    psd=np.full(FREQS.shape, 0.0123456),
    valid_seconds=26.0,
)
MIN_SPAN_S = 4.0
TRIM_S = 2.0


class FakeClock:
    def __init__(self, now: float = DATA_T0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class FakeAnalysis:
    """Records calls; tremor fails like the real one when the span is too short."""

    def __init__(self, *, unimplemented: bool = False) -> None:
        self.unimplemented = unimplemented
        self.tremor_calls: list[dict[str, Any]] = []
        self.posture_bands: list[tuple[float, float]] = []

    def tremor(self, t: np.ndarray, acc: np.ndarray, *, trim: bool = True) -> TremorResult:
        if self.unimplemented:
            raise NotImplementedError
        self.tremor_calls.append({"n": len(t), "trim": trim})
        span = float(t[-1] - t[0]) if len(t) > 1 else 0.0
        if span - (2 * TRIM_S if trim else 0.0) < MIN_SPAN_S:
            raise AnalysisError("insufficient_valid_data")
        return dataclasses.replace(FIXED, valid_seconds=span)

    def posture(
        self,
        t_imu: np.ndarray,
        acc: np.ndarray,
        t_tof: np.ndarray,
        mm: np.ndarray,
        band: tuple[float, float],
    ) -> TremorResult:
        self.posture_bands.append(band)
        return FIXED

    def reach(self, *args: Any) -> ReachResult:
        raise NotImplementedError

    def tap(self, *args: Any) -> TapResult:
        raise NotImplementedError

    def bundle(self) -> Analyzers:
        return Analyzers(tremor=self.tremor, posture=self.posture, reach=self.reach, tap=self.tap)


class QuietSource:
    """A source that never yields, so tests feed the broadcaster through dispatch()."""

    name = "sim"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def batches(self) -> AsyncIterator[Batch]:
        await asyncio.Event().wait()
        return
        yield  # makes this an async generator

    async def led(self, command: LedCommand, value: int | None) -> None:
        return None

    def health(self) -> SourceHealth:
        return SourceHealth(True, {"movement": True, "distance": True}, None, None)


def sim_batches(
    seconds: float, params: SimParams | None = None, *, seed: int = 0, t0: float = DATA_T0
) -> list[ImuBatch | TofBatch]:
    """`seconds` of fast simulator IMU+ToF batches, timestamps shifted to start at t0."""

    async def go() -> list[ImuBatch | TofBatch]:
        source = SimulatedSource(params or SimParams(), fast=True, seed=seed)
        await source.start()
        out: list[ImuBatch | TofBatch] = []
        async for b in source.batches():
            if isinstance(b, ImuBatch | TofBatch):
                out.append(b)
            if len(out) >= 2 * round(seconds * 10):
                break
        return out

    batches = asyncio.run(go())
    shift = t0 - float(batches[0].t[0])
    return [dataclasses.replace(b, t=b.t + shift) for b in batches]
