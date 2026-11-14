"""SensorSource protocol and batch types. Sources emit SI units with epoch-second timestamps."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol

import numpy as np
from numpy.typing import NDArray

LedCommand = Literal["countdown", "hold", "check", "idle", "clear", "recording"]


@dataclass(frozen=True)
class ImuBatch:
    """t: (N,) epoch s; acc: (N, 3) m/s²; gyro: (N, 3) deg/s."""

    t: NDArray[np.float64]
    acc: NDArray[np.float64]
    gyro: NDArray[np.float64]


@dataclass(frozen=True)
class TofBatch:
    """t: (N,) epoch s; mm: (N,) distance in mm (NaN when invalid)."""

    t: NDArray[np.float64]
    mm: NDArray[np.float64]


@dataclass(frozen=True)
class SourceStatus:
    """Link or sensor state change; sensors maps "movement"/"distance" to detected."""

    connected: bool
    sensors: dict[str, bool] = field(default_factory=dict)
    message: str | None = None


Batch = ImuBatch | TofBatch | SourceStatus


@dataclass(frozen=True)
class SourceHealth:
    """Current link state; rates in Hz measured from timestamps, None when unknown."""

    connected: bool
    sensors_detected: dict[str, bool]
    imu_hz: float | None
    tof_hz: float | None


class SensorSource(Protocol):
    name: str

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    def batches(self) -> AsyncIterator[Batch]: ...

    async def led(self, command: LedCommand, value: int | None) -> None: ...

    def health(self) -> SourceHealth: ...
