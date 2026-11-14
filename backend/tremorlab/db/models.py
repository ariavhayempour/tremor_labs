"""Row dataclasses returned by db.queries, and the literal types shared across the backend."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

TestType = Literal["rest", "posture", "reach", "tap"]
Hand = Literal["left", "right"]
TestStatus = Literal["recording", "analyzing", "done", "failed"]
FailReason = Literal[
    "insufficient_valid_data",
    "no_descent_detected",
    "no_taps_detected",
    "sensor_disconnected",
    "interrupted",
]
Sensor = Literal["imu", "tof"]


@dataclass(frozen=True)
class CheckRow:
    id: int
    created_at: datetime
    minutes_since_dose: float | None
    caffeine: bool | None
    sleep_quality: int | None
    stress: int | None
    alcohol: bool | None
    notes: str | None
    dose_id: int | None


@dataclass(frozen=True)
class TestRow:
    __test__ = False  # not a pytest test class

    id: int
    check_id: int
    type: TestType
    hand: Hand
    started_at: datetime
    ended_at: datetime | None
    status: TestStatus
    fail_reason: FailReason | None
    markers: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class ResultRow:
    """One test's result. Units: Hz, m/s², 0-100 score, mm, taps/s, ratios unitless, seconds."""

    peak_hz: float | None = None
    strength_ms2: float | None = None
    strength_score: float | None = None
    tremor_detected: bool | None = None
    smoothness: float | None = None
    wobble_ratio: float | None = None
    taps_per_sec: float | None = None
    tap_amplitude: float | None = None
    amplitude_decrement: float | None = None
    rhythm_cv: float | None = None
    valid_seconds: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DoseRow:
    id: int
    taken_at: datetime
    label: str | None
