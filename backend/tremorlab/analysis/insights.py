"""Dashboard and report insights over stored observations."""

import math
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from statistics import fmean

DOSE_BIN_H = 0.5
DOSE_MAX_H = 6.0
RETURNS_MIN_COUNT = 3
RETURNS_MIN_H = 1.0
PROFILE_FIRST_DAYS = 7
PROFILE_CURRENT_DAYS = 3
POOR_SLEEP_MAX = 2
HIGH_STRESS_MIN = 4

REST = "rest"
PROFILE_TEST_TYPES = ("rest", "posture", "reach", "tap")
BIN_EPS = 1e-9


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


def _rest(obs: Sequence[Obs]) -> list[Obs]:
    return [o for o in obs if o.test_type == REST and math.isfinite(o.metric)]


def _mean_or_none(values: Sequence[float]) -> float | None:
    return fmean(values) if values else None


def dose_response(
    obs: Sequence[Obs], bin_h: float = DOSE_BIN_H, max_h: float = DOSE_MAX_H
) -> list[Bin]:
    """Rest strength_ms2 binned by hours since dose; observations without a dose are skipped.

    Metric: rest strength_ms2 (m/s²). Bins [k·bin_h, (k+1)·bin_h) h cover [0, max_h); empty ones
    are omitted; sorted by start_h.
    """
    groups: dict[int, list[float]] = defaultdict(list)
    for o in _rest(obs):
        if o.minutes_since_dose is None:
            continue
        h = o.minutes_since_dose / 60.0
        if 0.0 <= h < max_h:
            groups[math.floor(h / bin_h + BIN_EPS)].append(o.metric)
    return [Bin(round(k * bin_h, 6), fmean(v), len(v)) for k, v in sorted(groups.items())]


def returns_after_h(
    bins: Sequence[Bin], overall_median: float, min_count: int = RETURNS_MIN_COUNT
) -> float | None:
    """First bin at ≥1 h whose mean exceeds overall_median with ≥min_count samples, in hours.

    overall_median is in the bins' units (m/s²); returns the bin's start_h, or None.
    """
    for b in sorted(bins, key=lambda b: b.start_h):
        if (
            b.start_h >= RETURNS_MIN_H - BIN_EPS
            and b.count >= min_count
            and b.mean > overall_median
        ):
            return b.start_h
    return None


_FACTORS: tuple[tuple[str, tuple[tuple[str, Callable[[Obs], bool]], ...]], ...] = (
    ("caffeine", (("yes", lambda o: o.caffeine is True), ("no", lambda o: o.caffeine is False))),
    (
        "sleep",
        (
            ("poor", lambda o: o.sleep_quality is not None and o.sleep_quality <= POOR_SLEEP_MAX),
            ("ok", lambda o: o.sleep_quality is not None and o.sleep_quality > POOR_SLEEP_MAX),
        ),
    ),
    (
        "stress",
        (
            ("high", lambda o: o.stress is not None and o.stress >= HIGH_STRESS_MIN),
            ("low", lambda o: o.stress is not None and o.stress < HIGH_STRESS_MIN),
        ),
    ),
    ("alcohol", (("yes", lambda o: o.alcohol is True), ("no", lambda o: o.alcohol is False))),
)


def factor_effects(obs: Sequence[Obs]) -> list[FactorEffect]:
    """Rest strength split by caffeine yes/no, sleep poor/ok, stress high/low, alcohol yes/no.

    Metric: rest strength_ms2 (m/s²). Unanswered factors are skipped; empty groups are omitted.
    """
    rest = _rest(obs)
    out = []
    for factor, groups in _FACTORS:
        for group, member in groups:
            values = [o.metric for o in rest if member(o)]
            if values:
                out.append(FactorEffect(factor, group, fmean(values), len(values)))
    return out


def profile(obs: Sequence[Obs], now: datetime) -> list[ProfileRow]:
    """Per test type: mean over the first 7 days from the first check vs the last 3 days.

    Metric per type is the Results-card metric (score, mm, taps/s). Windows: [first, first+7 d)
    and (now-3 d, now]; observations after now are ignored. Always rest, posture, reach, tap.
    """
    past = [o for o in obs if o.created_at <= now and math.isfinite(o.metric)]
    first_end = min((o.created_at for o in past), default=now) + timedelta(days=PROFILE_FIRST_DAYS)
    current_start = now - timedelta(days=PROFILE_CURRENT_DAYS)
    rows = []
    for test_type in PROFILE_TEST_TYPES:
        mine = [o for o in past if o.test_type == test_type]
        first = [o.metric for o in mine if o.created_at < first_end]
        current = [o.metric for o in mine if o.created_at > current_start]
        rows.append(
            ProfileRow(
                test_type, _mean_or_none(first), len(first), _mean_or_none(current), len(current)
            )
        )
    return rows


def daily_timeline(obs: Sequence[Obs], tz: tzinfo) -> list[DayPoint]:
    """Mean rest strength per local calendar day.

    Metric: rest strength_ms2 (m/s²). One point per local day that has any observation, oldest
    first; count is the day's rest observations and mean_rest is None when it is 0.
    """
    days: dict[date, list[float]] = defaultdict(list)
    for o in obs:
        values = days[o.created_at.astimezone(tz).date()]
        if o.test_type == REST and math.isfinite(o.metric):
            values.append(o.metric)
    return [DayPoint(d.isoformat(), _mean_or_none(v), len(v)) for d, v in sorted(days.items())]


def streak_days(check_dates: Sequence[date], today: date) -> int:
    """Consecutive calendar days with at least one check, ending today.

    A today with no check yet does not break the streak: counting then ends yesterday.
    """
    seen = set(check_dates)
    day = today if today in seen else today - timedelta(days=1)
    count = 0
    while day in seen:
        count += 1
        day -= timedelta(days=1)
    return count
