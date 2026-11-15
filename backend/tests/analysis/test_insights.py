from datetime import UTC, date, datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

import pytest

from tremorlab.analysis.insights import (
    Bin,
    DayPoint,
    Obs,
    ProfileRow,
    daily_timeline,
    dose_response,
    profile,
    returns_after_h,
    streak_days,
)
from tremorlab.seeding import SeedData, generate

T0 = datetime(2026, 11, 1, 15, 0, tzinfo=UTC)
CHICAGO = ZoneInfo("America/Chicago")


def _obs(
    metric: float,
    minutes: float | None = 60.0,
    test_type: str = "rest",
    at: datetime = T0,
) -> Obs:
    return Obs(
        minutes_since_dose=minutes,
        created_at=at,
        test_type=test_type,
        metric=metric,
    )


def test_bins_half_hour_with_counts() -> None:
    obs = [
        _obs(0.10, minutes=10),
        _obs(0.20, minutes=29.9),
        _obs(0.30, minutes=30),  # a lower edge belongs to its own bin
        _obs(0.50, minutes=200),
        _obs(0.70, minutes=210),
        _obs(0.90, minutes=359.9),
        _obs(9.00, minutes=360),  # at max_h: outside
        _obs(9.00, minutes=None),
        _obs(9.00, minutes=-5),
        _obs(9.00, minutes=60, test_type="posture"),
    ]
    bins = dose_response(obs)
    assert [b.start_h for b in bins] == [0.0, 0.5, 3.0, 3.5, 5.5]
    assert [b.count for b in bins] == [2, 1, 1, 1, 1]
    assert bins[0].mean == pytest.approx(0.15)
    assert all(isinstance(b, Bin) for b in bins)


def test_bins_custom_width_and_empty() -> None:
    assert dose_response([]) == []
    bins = dose_response([_obs(1.0, minutes=50), _obs(3.0, minutes=70)], bin_h=1.0, max_h=2.0)
    assert bins == [Bin(0.0, 1.0, 1), Bin(1.0, 3.0, 1)]


def test_returns_after_requires_min_count() -> None:
    bins = [
        Bin(0.0, 0.50, 5),  # before 1 h: ignored even though high
        Bin(1.0, 0.10, 5),
        Bin(1.5, 0.40, 2),  # high but only 2 samples
        Bin(2.0, 0.20, 4),  # equal to the median: not above it
        Bin(2.5, 0.30, 3),
        Bin(3.0, 0.40, 6),
    ]
    assert returns_after_h(bins, overall_median=0.20) == 2.5
    assert returns_after_h(bins, overall_median=0.20, min_count=2) == 1.5
    assert returns_after_h(bins, overall_median=1.0) is None
    assert returns_after_h([], overall_median=0.1) is None


def test_returns_after_uses_bin_order_not_list_order() -> None:
    bins = [Bin(3.0, 0.4, 3), Bin(2.0, 0.4, 3)]
    assert returns_after_h(bins, overall_median=0.2) == 2.0


def test_profile_windows() -> None:
    first = datetime(2026, 11, 1, 14, 0, tzinfo=UTC)
    now = first + timedelta(days=13, hours=6)
    obs = [
        _obs(10.0, at=first),
        _obs(20.0, at=first + timedelta(days=6, hours=23)),
        _obs(99.0, at=first + timedelta(days=7)),  # just past the first week
        _obs(40.0, at=now - timedelta(days=2)),
        _obs(50.0, at=now),
        _obs(77.0, at=now - timedelta(days=3, minutes=1)),  # just before the current window
        _obs(5.0, test_type="tap", at=now - timedelta(hours=1)),
        _obs(3.0, test_type="reach", at=first + timedelta(days=1)),
    ]
    rows = profile(obs, now)
    assert [r.test_type for r in rows] == ["rest", "posture", "reach", "tap"]
    assert rows[0] == ProfileRow("rest", 15.0, 2, 45.0, 2)
    assert rows[1] == ProfileRow("posture", None, 0, None, 0)
    assert rows[2] == ProfileRow("reach", 3.0, 1, None, 0)
    assert rows[3] == ProfileRow("tap", None, 0, 5.0, 1)


def test_profile_ignores_future_and_handles_empty() -> None:
    now = T0
    rows = profile([_obs(1.0, at=now), _obs(9.0, at=now + timedelta(minutes=1))], now)
    assert rows[0] == ProfileRow("rest", 1.0, 1, 1.0, 1)
    assert profile([], now) == [
        ProfileRow(t, None, 0, None, 0) for t in ("rest", "posture", "reach", "tap")
    ]


def test_daily_timeline_groups_by_local_day_across_dst() -> None:
    obs = [
        # 2026-11-01 05:30Z is 00:30 CDT and 2026-11-02 05:30Z is 23:30 CST: both on Nov 1.
        _obs(0.10, at=datetime(2026, 11, 1, 5, 30, tzinfo=UTC)),
        _obs(0.30, at=datetime(2026, 11, 2, 5, 30, tzinfo=UTC)),
        _obs(0.20, at=datetime(2026, 11, 2, 6, 30, tzinfo=UTC)),
        _obs(9.00, test_type="tap", at=datetime(2026, 11, 2, 6, 31, tzinfo=UTC)),
        _obs(9.00, test_type="tap", at=datetime(2026, 11, 4, 18, 0, tzinfo=UTC)),
        _obs(0.40, at=datetime(2026, 10, 31, 20, 0, tzinfo=UTC)),
    ]
    assert daily_timeline(obs, CHICAGO) == [
        DayPoint("2026-10-31", 0.40, 1),
        DayPoint("2026-11-01", 0.20, 2),
        DayPoint("2026-11-02", 0.20, 1),
        DayPoint("2026-11-04", None, 0),
    ]
    assert daily_timeline([], CHICAGO) == []


def test_streak_counts_consecutive_days_ending_today() -> None:
    today = date(2026, 11, 14)
    days = [today - timedelta(days=i) for i in (0, 1, 1, 2, 4, 5)]
    assert streak_days(days, today) == 3
    assert streak_days([today], today) == 1
    assert streak_days([], today) == 0


def test_streak_survives_today_without_a_check_yet() -> None:
    today = date(2026, 11, 14)
    yesterday_run = [today - timedelta(days=i) for i in (1, 2, 3)]
    assert streak_days(yesterday_run, today) == 3
    assert streak_days([today - timedelta(days=2)], today) == 0
    assert streak_days([today + timedelta(days=1)], today) == 0


def test_streak_over_dst_change() -> None:
    today = date(2026, 11, 2)
    assert streak_days([date(2026, 10, 31), date(2026, 11, 1), today], today) == 3


def _rest_obs(data: SeedData) -> list[Obs]:
    out = []
    for c in data.checks:
        for t in c.tests:
            if t.type == "rest" and t.result.strength_ms2 is not None:
                out.append(
                    Obs(
                        minutes_since_dose=c.minutes_since_dose,
                        created_at=c.created_at,
                        test_type="rest",
                        metric=t.result.strength_ms2,
                    )
                )
    return out


def test_dose_response_on_seeded_data_shows_rise() -> None:
    obs = _rest_obs(generate(seed=42, days=14, end=date(2026, 11, 14), tz=CHICAGO))
    bins = dose_response(obs)
    binned = [
        o.metric for o in obs if o.minutes_since_dose is not None and o.minutes_since_dose < 360
    ]
    assert sum(b.count for b in bins) == len(binned)
    found = returns_after_h(bins, median(binned))
    assert found is not None and 2.0 <= found <= 4.0
    early = [b.mean for b in bins if 1.0 <= b.start_h < 2.0]
    late = [b.mean for b in bins if 3.5 <= b.start_h < 5.0]
    assert max(early) < min(late)
