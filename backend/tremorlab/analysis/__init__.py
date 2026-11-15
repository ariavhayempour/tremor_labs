"""Pure analysis functions (no I/O, no clock, no DB) and the bundle the test session consumes."""

from collections.abc import Callable
from dataclasses import dataclass

from tremorlab.analysis.reach import ReachResult
from tremorlab.analysis.tap import TapResult
from tremorlab.analysis.tremor import TremorResult


@dataclass(frozen=True)
class Analyzers:
    tremor: Callable[..., TremorResult]
    posture: Callable[..., TremorResult]
    reach: Callable[..., ReachResult]
    tap: Callable[..., TapResult]
    remote: bool = False  # calls go over the network, so keep them off the event loop
