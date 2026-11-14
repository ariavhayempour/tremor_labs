"""Deterministic 14-day demo data (pure: no DB, no clock). Written to SQLite by db.seed_writer."""

from dataclasses import dataclass, field
from datetime import date, datetime, tzinfo

from tremorlab.db.models import Hand, ResultRow, TestType

DOSE_TIMES_LOCAL = ("08:00", "13:00", "18:00")
DOSE_JITTER_MIN = 10.0
CHECKS_PER_DAY = (3, 4)
CHECK_WINDOW_LOCAL = ("07:30", "21:30")


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
    caffeine: bool | None
    sleep_quality: int | None
    stress: int | None
    alcohol: bool | None
    dose_index: int | None
    tests: list[SeedTest] = field(default_factory=list)


@dataclass(frozen=True)
class SeedData:
    doses: list[SeedDose]
    checks: list[SeedCheck]


def generate(
    seed: int = 42, days: int = 14, end: date | None = None, tz: tzinfo | None = None
) -> SeedData:
    """Seeded doses, checks, tests, results; UTC-aware datetimes; day logic in tz (None = local)."""
    raise NotImplementedError
