"""Simulated IMU (100 Hz) and ToF (40 Hz) source for development without hardware."""

from collections.abc import AsyncIterator

from tremorlab.config import SimParams
from tremorlab.sources.base import Batch, LedCommand, SourceHealth


class SimulatedSource:
    name = "sim"

    def __init__(self, params: SimParams, *, fast: bool = False, seed: int | None = None) -> None:
        raise NotImplementedError

    @property
    def params(self) -> SimParams:
        raise NotImplementedError

    def set_params(self, **changes: float) -> SimParams:
        """Apply changes from the next batch on; returns the new params."""
        raise NotImplementedError

    def trigger_descent(self) -> None:
        """Script a 300 → 30 mm ToF descent over 2.5 s, with reach_wobble in the last 50 mm."""
        raise NotImplementedError

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    def batches(self) -> AsyncIterator[Batch]:
        raise NotImplementedError

    async def led(self, command: LedCommand, value: int | None) -> None:
        raise NotImplementedError

    def health(self) -> SourceHealth:
        raise NotImplementedError
