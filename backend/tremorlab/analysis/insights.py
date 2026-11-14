"""Dashboard and report insights over stored observations."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, tzinfo

DOSE_BIN_H = 0.5
DOSE_MAX_H = 6.0
RETURNS_MIN_COUNT = 3
RETURNS_MIN_H = 1.0
PROFILE_FIRST_DAYS = 7
PROFILE_CURRENT_DAYS = 3
POOR_SLEEP_MAX = 2
HIGH_STRESS_MIN = 4


@dataclass(frozen=True)
class Obs:
    """One done test's metric with its check context; metric units depend on test_type."""

    minutes_since_dose: float | None
    created_at: datetime
    caffeine: bool | None
    sleep_quality: int | None
    stress: int | None
    alcohol: bool | None
    test_type: str
    metric: float


@dataclass(frozen=True)
class Bin:
    """start_h hours since dose; mean rest strength m/s²; count observations."""

    start_h: float
    mean: float
    count: int


@dataclass(frozen=True)
class FactorEffect:
    factor: str
    group: str
    mean: float
    count: int


@dataclass(frozen=True)
class ProfileRow:
    test_type: str
    first_week: float | None
    first_n: int
    current: float | None
    current_n: int


@dataclass(frozen=True)
class DayPoint:
    """date YYYY-MM-DD (local); mean_rest m/s² or None; count observations."""

    date: str
    mean_rest: float | None
    count: int


def dose_response(
    obs: Sequence[Obs], bin_h: float = DOSE_BIN_H, max_h: float = DOSE_MAX_H
) -> list[Bin]:
    """Rest strength_ms2 binned by hours since dose; observations without a dose are skipped."""
    raise NotImplementedError


def returns_after_h(
    bins: Sequence[Bin], overall_median: float, min_count: int = RETURNS_MIN_COUNT
) -> float | None:
    """First bin at ≥1 h whose mean exceeds overall_median with ≥min_count samples, in hours."""
    raise NotImplementedError


def factor_effects(obs: Sequence[Obs]) -> list[FactorEffect]:
    """Rest strength split by caffeine yes/no, sleep poor/ok, stress high/low, alcohol yes/no."""
    raise NotImplementedError


def profile(obs: Sequence[Obs], now: datetime) -> list[ProfileRow]:
    """Per test type: mean over the first 7 days from the first check vs the last 3 days."""
    raise NotImplementedError


def daily_timeline(obs: Sequence[Obs], tz: tzinfo) -> list[DayPoint]:
    """Mean rest strength per local calendar day."""
    raise NotImplementedError


def streak_days(check_dates: Sequence[date], today: date) -> int:
    """Consecutive calendar days with at least one check, ending today."""
    raise NotImplementedError
