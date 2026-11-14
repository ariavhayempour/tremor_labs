"""BoardSource: NDJSON TCP client for the UNO Q relay (wire protocol in docs/contracts.md)."""

import time
from collections.abc import AsyncIterator, Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray

from tremorlab.sources.base import Batch, LedCommand, SourceHealth


def parse_line(line: bytes) -> dict[str, Any] | None:
    """Decode one NDJSON line; None for malformed input."""
    raise NotImplementedError


class MicrosUnwrapper:
    """Turns 32-bit micros() values into seconds since the first sample, across 2³² rollover."""

    def __call__(self, t_us: NDArray[np.int64]) -> NDArray[np.float64]:
        raise NotImplementedError


def decode_imu(d: list[int]) -> tuple[NDArray[np.int64], NDArray[np.float64], NDArray[np.float64]]:
    """Flat [t_us, ax_mg, ay_mg, az_mg, gx_mdps, gy_mdps, gz_mdps, ...] → (t_us, m/s², deg/s)."""
    raise NotImplementedError


def decode_tof(d: list[int]) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
    """Flat [t_us, mm, ...] → (t_us, mm)."""
    raise NotImplementedError


class BoardSource:
    name = "board"

    def __init__(self, host: str, port: int, *, clock: Callable[[], float] = time.time) -> None:
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
