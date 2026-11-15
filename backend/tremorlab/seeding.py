"""Deterministic 14-day demo data (pure: no DB, no clock). Written to SQLite by db.seed_writer."""

import bisect
import itertools
import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, tzinfo

import numpy as np

from tremorlab.analysis.posture import POSTURE_RMS_MIN_MS2
from tremorlab.analysis.sampling import TRIM_SECONDS
from tremorlab.analysis.tremor import RMS_MIN_MS2, strength_to_score
from tremorlab.db.models import Hand, ResultRow, TestType

DOSE_TIMES_LOCAL = ("08:00", "13:00", "18:00")
DOSE_JITTER_MIN = 10.0
CHECKS_PER_DAY = (3, 4)
CHECK_WINDOW_LOCAL = ("07:30", "21:30")
CHECK_MIN_GAP_MIN = 30.0

STRENGTH_FLOOR_MS2 = 0.06
STRENGTH_RANGE_MS2 = 0.34
WEAR_OFF_MID_H = 3.0
WEAR_OFF_WIDTH_H = 0.5
ONSET_H = 1.0
NOISE_SIGMA = 0.12
POSTURE_FACTOR = 0.7
PEAK_HZ_RANGE = (4.5, 5.5)

REF_STRENGTH_MS2 = 0.4
REACH_SMOOTHNESS_MM = (2.0, 4.0)
REACH_WOBBLE = (1.0, 1.5)
TAP_RATE_PER_S = (4.2, -0.8)
TAP_AMPLITUDE = (1.0, -0.2)
TAP_DECREMENT_RANGE = (-0.15, -0.05)
TAP_RHYTHM_CV = (0.08, 0.1)

REST_RECORD_S = 30.0
POSTURE_VALID_S_RANGE = (22.0, 30.0)
TESTED_HAND: Hand = "right"
TEST_PLAN: tuple[tuple[TestType, Hand, float], ...] = (
    ("rest", TESTED_HAND, 15.0),
    ("posture", TESTED_HAND, 60.0),
    ("reach", TESTED_HAND, 110.0),
    ("tap", "left", 150.0),
    ("tap", "right", 175.0),
)


@dataclass(frozen=True)
class SeedDose:
    taken_at: datetime
    label: str | None = None


@dataclass(frozen=True)
class SeedTest:
    type: TestType
    hand: Hand
    started_at: datetime
    result: ResultRow


@dataclass(frozen=True)
class SeedCheck:
    """dose_index points into SeedData.doses (the latest dose at or before created_at)."""

    created_at: datetime
    minutes_since_dose: float | None
    dose_index: int | None
    tests: list[SeedTest] = field(default_factory=list)


@dataclass(frozen=True)
class SeedData:
    doses: list[SeedDose]
    checks: list[SeedCheck]


def _minutes(hhmm: str) -> float:
    h, m = hhmm.split(":")
    return int(h) * 60.0 + int(m)


def _to_utc(day: date, minutes: float, tz: tzinfo | None) -> datetime:
    """Local wall time (minutes after midnight on day) → UTC; tz None uses the Mac's local zone."""
    wall = datetime(day.year, day.month, day.day) + timedelta(minutes=minutes)
    local = wall.replace(tzinfo=tz) if tz is not None else wall.astimezone()
    return local.astimezone(UTC).replace(microsecond=0)


def _base_ms2(h: float) -> float:
    """Wearing-off curve: rest strength in m/s² h hours after a dose."""
    return STRENGTH_FLOOR_MS2 + STRENGTH_RANGE_MS2 / (
        1.0 + math.exp(-(h - WEAR_OFF_MID_H) / WEAR_OFF_WIDTH_H)
    )


def _clean_ms2(h: float | None, prev_interval_h: float | None) -> float:
    """Noise-free rest strength in m/s²; before ONSET_H it falls from the pre-dose value."""
    if h is None:
        return STRENGTH_FLOOR_MS2 + STRENGTH_RANGE_MS2
    if h >= ONSET_H:
        return _base_ms2(h)
    before = (
        STRENGTH_FLOOR_MS2 + STRENGTH_RANGE_MS2
        if prev_interval_h is None
        else _base_ms2(prev_interval_h)
    )
    return before + (STRENGTH_FLOOR_MS2 - before) * (h / ONSET_H)


def _check_minutes(rng: np.random.Generator) -> list[float]:
    """3-4 sorted local check times (minutes after midnight), at least CHECK_MIN_GAP_MIN apart."""
    n = int(rng.integers(CHECKS_PER_DAY[0], CHECKS_PER_DAY[-1] + 1))
    lo, hi = (_minutes(s) for s in CHECK_WINDOW_LOCAL)
    while True:
        times = sorted(round(float(x), 1) for x in rng.uniform(lo, hi, n))
        if all(b - a >= CHECK_MIN_GAP_MIN for a, b in itertools.pairwise(times)):
            return times


def _tremor_row(
    rng: np.random.Generator, strength: float, gate: float, valid_s: float
) -> ResultRow:
    detected = strength >= gate
    return ResultRow(
        peak_hz=round(float(rng.uniform(*PEAK_HZ_RANGE)), 2) if detected else None,
        strength_ms2=strength,
        strength_score=strength_to_score(strength),
        tremor_detected=detected,
        valid_seconds=valid_s,
    )


def _tap_row(rng: np.random.Generator, rel: float) -> ResultRow:
    return ResultRow(
        taps_per_sec=round(TAP_RATE_PER_S[0] + TAP_RATE_PER_S[1] * rel, 3),
        tap_amplitude=round(TAP_AMPLITUDE[0] + TAP_AMPLITUDE[1] * rel, 3),
        amplitude_decrement=round(float(rng.uniform(*TAP_DECREMENT_RANGE)), 3),
        rhythm_cv=round(TAP_RHYTHM_CV[0] + TAP_RHYTHM_CV[1] * rel, 3),
    )


def _tests(rng: np.random.Generator, created_at: datetime, rest: float) -> list[SeedTest]:
    """All five tests of one check; reach and tap scale with rest strength ÷ REF_STRENGTH_MS2."""
    rel = rest / REF_STRENGTH_MS2
    posture = round(POSTURE_FACTOR * rest, 4)
    posture_valid = round(float(rng.uniform(*POSTURE_VALID_S_RANGE)), 1)
    rows: dict[TestType, ResultRow] = {
        "rest": _tremor_row(rng, rest, RMS_MIN_MS2, REST_RECORD_S - 2 * TRIM_SECONDS),
        "posture": _tremor_row(rng, posture, POSTURE_RMS_MIN_MS2, posture_valid),
        "reach": ResultRow(
            smoothness=round(REACH_SMOOTHNESS_MM[0] + REACH_SMOOTHNESS_MM[1] * rel, 3),
            wobble_ratio=round(REACH_WOBBLE[0] + REACH_WOBBLE[1] * rel, 3),
        ),
    }
    out = []
    for test_type, hand, offset_s in TEST_PLAN:
        result = _tap_row(rng, rel) if test_type == "tap" else rows[test_type]
        started = created_at + timedelta(seconds=offset_s)
        out.append(SeedTest(type=test_type, hand=hand, started_at=started, result=result))
    return out


def generate(
    seed: int = 42, days: int = 14, end: date | None = None, tz: tzinfo | None = None
) -> SeedData:
    """Seeded doses, checks, tests, results; UTC-aware datetimes; day logic in tz (None = local).

    The last seeded day is end (default: today in tz), inclusive.
    """
    rng = np.random.default_rng(seed)
    last = end if end is not None else datetime.now(tz).date()
    day_list = [last - timedelta(days=days - 1 - i) for i in range(days)]

    doses = [
        SeedDose(
            taken_at=_to_utc(
                day, _minutes(t) + float(rng.uniform(-DOSE_JITTER_MIN, DOSE_JITTER_MIN)), tz
            )
        )
        for day in day_list
        for t in DOSE_TIMES_LOCAL
    ]
    dose_times = [d.taken_at for d in doses]

    checks = []
    for day in day_list:
        for minutes in _check_minutes(rng):
            created_at = _to_utc(day, minutes, tz)
            idx = bisect.bisect_right(dose_times, created_at) - 1
            since_min = (created_at - dose_times[idx]).total_seconds() / 60.0 if idx >= 0 else None
            prev_h = (
                (dose_times[idx] - dose_times[idx - 1]).total_seconds() / 3600.0
                if idx >= 1
                else None
            )
            clean = _clean_ms2(None if since_min is None else since_min / 60.0, prev_h)
            rest = round(clean * float(rng.lognormal(0.0, NOISE_SIGMA)), 4)
            checks.append(
                SeedCheck(
                    created_at=created_at,
                    minutes_since_dose=since_min,
                    dose_index=idx if idx >= 0 else None,
                    tests=_tests(rng, created_at, rest),
                )
            )
    return SeedData(doses=doses, checks=checks)
