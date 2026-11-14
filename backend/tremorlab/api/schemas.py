"""Pydantic request/response models. docs/contracts.md documents each one; keep them in sync."""

import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from tremorlab.db.models import FailReason, Hand, TestStatus, TestType
from tremorlab.sources.base import LedCommand

Score1to5 = Annotated[int, Field(ge=1, le=5)]
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorOut(Model):
    error: str
    message: str


class SensorsDetected(Model):
    movement: bool
    distance: bool


class HealthOut(Model):
    status: Literal["ok"]
    sensor_source: Literal["sim", "board", "replay"]
    connected: bool
    sensors_detected: SensorsDetected
    imu_hz: float | None
    tof_hz: float | None


class SimParamsOut(Model):
    tremor_hz: float
    tremor_amp: float
    noise: float
    hand_mm: float
    reach_wobble: float


class SimUpdateRequest(Model):
    """Partial SimParams, or {"action": "descent"} to script a reach descent."""

    tremor_hz: float | None = Field(default=None, gt=0, le=30)
    tremor_amp: float | None = Field(default=None, ge=0, le=5)
    noise: float | None = Field(default=None, ge=0, le=1)
    hand_mm: float | None = Field(default=None, ge=0, le=2000)
    reach_wobble: float | None = Field(default=None, ge=0, le=50)
    action: Literal["descent"] | None = None


class CheckInRequest(Model):
    medication: Literal["now", "hours_ago", "not_yet"]
    hours_ago: float | None = Field(default=None, ge=0, le=24)
    caffeine: bool | None = None
    sleep_quality: Score1to5 | None = None
    stress: Score1to5 | None = None
    alcohol: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CheckCreated(Model):
    check_id: int
    minutes_since_dose: float | None


class StartTestRequest(Model):
    type: TestType
    hand: Hand


class TestStarted(Model):
    __test__ = False  # not a pytest test class

    test_id: int


class ResultOut(Model):
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
    details: dict[str, Any] = Field(default_factory=dict)


class TestOutcomeOut(Model):
    __test__ = False  # not a pytest test class

    test_id: int
    status: Literal["done", "failed"]
    fail_reason: FailReason | None
    result: ResultOut | None


class TapFrameIn(Model):
    t_ms: float
    lm: list[Annotated[list[float], Field(min_length=2, max_length=2)]] | None = Field(
        default=None, min_length=4, max_length=4
    )


class TapDataIn(Model):
    frames: list[TapFrameIn] = Field(max_length=10_000)


class TestOut(Model):
    __test__ = False  # not a pytest test class

    id: int
    type: TestType
    hand: Hand
    status: TestStatus
    fail_reason: FailReason | None
    result: ResultOut | None


class CheckOut(Model):
    id: int
    created_at: datetime
    minutes_since_dose: float | None
    caffeine: bool | None
    sleep_quality: int | None
    stress: int | None
    alcohol: bool | None
    notes: str | None
    dose_id: int | None
    tests: list[TestOut]


class CardOut(Model):
    test: TestType
    metric: str
    value: float | None
    unit: str
    baseline_pct: float | None
    baseline_n: int
    status: str


class CheckSummaryOut(Model):
    check: CheckOut
    cards: list[CardOut]


class DoseOut(Model):
    id: int
    taken_at: datetime
    label: str | None


class Bin(Model):
    start_h: float
    mean: float
    count: int


class DoseResponseOut(Model):
    bins: list[Bin]
    returns_after_h: float | None
    doses: list[DoseOut]


class FactorEffect(Model):
    factor: Literal["caffeine", "sleep", "stress", "alcohol"]
    group: str
    mean: float
    count: int


class ProfileRow(Model):
    test_type: TestType
    first_week: float | None
    first_n: int
    current: float | None
    current_n: int


class DayPoint(Model):
    date: str
    mean_rest: float | None
    count: int


class InsightsSummary(Model):
    checks_completed: int
    streak_days: int
    returns_after_h: float | None
    daily: list[DayPoint]


class ReportPeriod(Model):
    start: datetime
    end: datetime


class ReportOut(Model):
    period: ReportPeriod
    checks_completed: int
    dose_response: list[Bin]
    returns_after_h: float | None
    factors: list[FactorEffect]
    profile: list[ProfileRow]
    daily: list[DayPoint]
    generated_at: datetime


def _check_times(values: list[str] | None) -> list[str] | None:
    for v in values or []:
        if not HHMM.match(v):
            raise ValueError(f"time must be HH:MM (24 h), got {v!r}")
    return values


def _check_band(band: tuple[float, float] | None) -> tuple[float, float] | None:
    if band is not None and not 0 <= band[0] < band[1] <= 2000:
        raise ValueError("posture_band must be [low_mm, high_mm] with 0 <= low < high <= 2000")
    return band


class SettingsModel(Model):
    dose_times: list[str] = Field(default_factory=lambda: ["08:00", "13:00", "18:00"])
    reminder_times: list[str] = Field(default_factory=list)
    tested_hand: Hand = "right"
    posture_band: tuple[float, float] | None = None

    check_times = field_validator("dose_times", "reminder_times")(_check_times)
    check_band = field_validator("posture_band")(_check_band)


class SettingsUpdate(Model):
    """Any subset of SettingsModel; omitted fields keep their stored value."""

    dose_times: list[str] | None = None
    reminder_times: list[str] | None = None
    tested_hand: Hand | None = None
    posture_band: tuple[float, float] | None = None

    check_times = field_validator("dose_times", "reminder_times")(_check_times)
    check_band = field_validator("posture_band")(_check_band)


class LedRequest(Model):
    command: LedCommand
    value: int | None = None
