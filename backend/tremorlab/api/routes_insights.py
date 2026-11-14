"""Dashboard insights over the done tests of the last `days` local calendar days."""

import sqlite3
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from fastapi import APIRouter, Query, Request

from tremorlab.analysis import insights
from tremorlab.api import schemas
from tremorlab.api.summary import CARD_METRICS, CARD_ORDER
from tremorlab.db import queries
from tremorlab.db.models import CheckRow, ResultRow, TestRow, TestType

router = APIRouter(prefix="/api/insights", tags=["insights"])
DAYS = Query(default=14, ge=1, le=365)
STRENGTH_FIELD = "strength_ms2"

Row = tuple[CheckRow, TestRow, ResultRow]


@dataclass(frozen=True)
class Window:
    """start = local midnight `days - 1` days before today, now = the app clock (both UTC)."""

    start: datetime
    now: datetime
    tz: tzinfo

    @property
    def today(self) -> date:
        return self.now.astimezone(self.tz).date()

    def dates(self) -> list[date]:
        """Every local calendar day in the window, oldest first."""
        first = self.start.astimezone(self.tz).date()
        return [first + timedelta(days=i) for i in range((self.today - first).days + 1)]


def local_tz(at: datetime) -> tzinfo:
    """The Mac's local UTC offset at `at`."""
    tz = at.astimezone().tzinfo
    assert tz is not None
    return tz


def window(request: Request, days: int) -> Window:
    """App state supplies `clock` (epoch s) and optionally `tz` (default: local time)."""
    clock: Callable[[], float] = request.app.state.clock
    now = datetime.fromtimestamp(clock(), UTC)
    tz: tzinfo = getattr(request.app.state, "tz", None) or local_tz(now)
    first = now.astimezone(tz).date() - timedelta(days=days - 1)
    return Window(datetime.combine(first, time(), tzinfo=tz).astimezone(UTC), now, tz)


def _conn(request: Request) -> sqlite3.Connection:
    conn: sqlite3.Connection = request.app.state.conn
    return conn


def load(conn: sqlite3.Connection, w: Window) -> list[Row]:
    return queries.done_metrics(conn, w.start, w.now)


def check_values(
    rows: Sequence[Row], test_type: TestType, field: str
) -> list[tuple[CheckRow, float]]:
    """One value per check: the latest done test's field; tap averages each hand's latest."""
    per_check: dict[int, tuple[CheckRow, dict[str, float]]] = {}
    for c, t, r in rows:
        value = getattr(r, field)
        if t.type != test_type or value is None:
            continue
        hand = t.hand if test_type == "tap" else "any"
        per_check.setdefault(c.id, (c, {}))[1][hand] = float(value)
    return [(c, sum(v.values()) / len(v)) for c, v in per_check.values()]


def to_obs(c: CheckRow, test_type: TestType, metric: float) -> insights.Obs:
    return insights.Obs(
        minutes_since_dose=c.minutes_since_dose,
        created_at=c.created_at,
        test_type=test_type,
        metric=metric,
    )


def rest_strength_obs(rows: Sequence[Row]) -> list[insights.Obs]:
    return [to_obs(c, "rest", v) for c, v in check_values(rows, "rest", STRENGTH_FIELD)]


def profile_obs(rows: Sequence[Row]) -> list[insights.Obs]:
    """Card metric per check and test type, in check order then card order."""
    found = [
        (c, kind, v)
        for kind in CARD_ORDER
        for c, v in check_values(rows, kind, CARD_METRICS[kind][0])
    ]
    found.sort(key=lambda x: (x[0].created_at, x[0].id, CARD_ORDER.index(x[1])))
    return [to_obs(c, kind, v) for c, kind, v in found]


def returns_after(bins: Sequence[insights.Bin], rest: Sequence[insights.Obs]) -> float | None:
    if not rest:
        return None
    return insights.returns_after_h(bins, statistics.median(o.metric for o in rest))


def daily(rest: Sequence[insights.Obs], w: Window) -> list[schemas.DayPoint]:
    points = {p.date: p for p in insights.daily_timeline(rest, w.tz)}
    out = []
    for d in w.dates():
        p = points.get(d.isoformat())
        count = 0 if p is None else p.count
        mean = None if p is None or count == 0 else p.mean_rest
        out.append(schemas.DayPoint(date=d.isoformat(), mean_rest=mean, count=count))
    return out


def profile_rows(rows: Sequence[Row], w: Window) -> list[schemas.ProfileRow]:
    """One row per test type in card order; types the insight omits report zero counts."""
    by_type = {p.test_type: p for p in insights.profile(profile_obs(rows), w.now)}
    out = []
    for kind in CARD_ORDER:
        p = by_type.get(kind)
        first_n, current_n = (0, 0) if p is None else (p.first_n, p.current_n)
        out.append(
            schemas.ProfileRow(
                test_type=kind,
                first_week=None if p is None or first_n == 0 else p.first_week,
                first_n=first_n,
                current=None if p is None or current_n == 0 else p.current,
                current_n=current_n,
            )
        )
    return out


def bins_out(bins: Sequence[insights.Bin]) -> list[schemas.Bin]:
    return [schemas.Bin(start_h=b.start_h, mean=b.mean, count=b.count) for b in bins if b.count]


@router.get("/dose-response")
async def dose_response(request: Request, days: int = DAYS) -> schemas.DoseResponseOut:
    conn, w = _conn(request), window(request, days)
    rest = rest_strength_obs(load(conn, w))
    bins = insights.dose_response(rest)
    return schemas.DoseResponseOut(
        bins=bins_out(bins),
        returns_after_h=returns_after(bins, rest),
        doses=[
            schemas.DoseOut(id=d.id, taken_at=d.taken_at, label=d.label)
            for d in queries.list_doses(conn, w.start, w.now)
        ],
    )


@router.get("/profile")
async def profile(request: Request, days: int = DAYS) -> list[schemas.ProfileRow]:
    w = window(request, days)
    return profile_rows(load(_conn(request), w), w)


@router.get("/summary")
async def summary(request: Request, days: int = DAYS) -> schemas.InsightsSummary:
    conn, w = _conn(request), window(request, days)
    rest = rest_strength_obs(load(conn, w))
    completed = queries.completed_check_times(conn, None, w.now)
    check_dates = sorted({t.astimezone(w.tz).date() for t in completed})
    return schemas.InsightsSummary(
        checks_completed=sum(t >= w.start for t in completed),
        streak_days=insights.streak_days(check_dates, w.today),
        returns_after_h=returns_after(insights.dose_response(rest), rest),
        daily=daily(rest, w),
    )
