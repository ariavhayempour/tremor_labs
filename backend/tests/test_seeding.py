from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from statistics import mean
from zoneinfo import ZoneInfo

import pytest

from tremorlab import seeding
from tremorlab.analysis.posture import POSTURE_RMS_MIN_MS2
from tremorlab.analysis.tremor import RMS_MIN_MS2, strength_to_score
from tremorlab.seeding import SeedCheck, SeedData, generate

TZ = ZoneInfo("America/Chicago")
END = date(2026, 11, 7)  # the window (10-25..11-07) crosses the 11-01 DST change in Chicago


@pytest.fixture(scope="module")
def data() -> SeedData:
    return generate(seed=42, days=14, end=END, tz=TZ)


EXPECTED_TESTS = [
    ("rest", "right"),
    ("posture", "right"),
    ("reach", "right"),
    ("tap", "left"),
    ("tap", "right"),
]


def _local_minutes(dt: datetime, tz: ZoneInfo) -> float:
    local = dt.astimezone(tz)
    return local.hour * 60 + local.minute + local.second / 60


def _hhmm(s: str) -> float:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _rest(check: SeedCheck) -> float:
    strength = next(t for t in check.tests if t.type == "rest").result.strength_ms2
    assert strength is not None
    return strength


def _hours(check: SeedCheck) -> float | None:
    return None if check.minutes_since_dose is None else check.minutes_since_dose / 60


def _in(check: SeedCheck, lo: float, hi: float) -> bool:
    h = _hours(check)
    return h is not None and lo <= h < hi


def test_deterministic(data: SeedData) -> None:
    again = generate(seed=42, days=14, end=END, tz=TZ)
    assert again == data
    assert generate(seed=7, days=14, end=END, tz=TZ) != data


def test_check_counts(data: SeedData) -> None:
    assert 42 <= len(data.checks) <= 56
    per_day: dict[date, int] = defaultdict(int)
    lo, hi = (_hhmm(s) for s in seeding.CHECK_WINDOW_LOCAL)
    for c in data.checks:
        per_day[c.created_at.astimezone(TZ).date()] += 1
        assert lo <= _local_minutes(c.created_at, TZ) <= hi
    assert sorted(per_day) == [END - timedelta(days=i) for i in range(13, -1, -1)]
    assert all(n in seeding.CHECKS_PER_DAY for n in per_day.values())
    assert [c.created_at for c in data.checks] == sorted(c.created_at for c in data.checks)


def test_doses_three_per_day(data: SeedData) -> None:
    assert len(data.doses) == 42
    per_day: dict[date, list[float]] = defaultdict(list)
    for d in data.doses:
        per_day[d.taken_at.astimezone(TZ).date()].append(_local_minutes(d.taken_at, TZ))
    assert len(per_day) == 14
    targets = [_hhmm(s) for s in seeding.DOSE_TIMES_LOCAL]
    for minutes in per_day.values():
        assert len(minutes) == 3
        for got, want in zip(sorted(minutes), targets, strict=True):
            assert abs(got - want) <= seeding.DOSE_JITTER_MIN + 1e-9


def test_dst_change_keeps_local_dose_times(data: SeedData) -> None:
    # 08:00 local is 13:00Z on CDT days and 14:00Z on CST days.
    before = [
        d.taken_at for d in data.doses if d.taken_at.astimezone(TZ).date() == date(2026, 10, 31)
    ]
    after = [
        d.taken_at for d in data.doses if d.taken_at.astimezone(TZ).date() == date(2026, 11, 2)
    ]
    assert 12.5 <= before[0].hour + before[0].minute / 60 <= 13.5
    assert 13.5 <= after[0].hour + after[0].minute / 60 <= 14.5


def test_datetimes_are_utc_aware(data: SeedData) -> None:
    stamps = [d.taken_at for d in data.doses] + [c.created_at for c in data.checks]
    stamps += [t.started_at for c in data.checks for t in c.tests]
    assert all(s.utcoffset() == timedelta(0) for s in stamps)


def test_dose_index_is_latest_dose_at_or_before_check(data: SeedData) -> None:
    for c in data.checks:
        earlier = [i for i, d in enumerate(data.doses) if d.taken_at <= c.created_at]
        if not earlier:
            assert c.dose_index is None and c.minutes_since_dose is None
            continue
        assert c.dose_index == earlier[-1]
        dose = data.doses[c.dose_index]
        assert c.minutes_since_dose == pytest.approx(
            (c.created_at - dose.taken_at).total_seconds() / 60
        )


def test_every_check_has_all_tests_in_order(data: SeedData) -> None:
    for c in data.checks:
        assert [(t.type, t.hand) for t in c.tests] == EXPECTED_TESTS
        starts = [t.started_at for t in c.tests]
        assert starts == sorted(starts) and starts[0] >= c.created_at
        assert all(t.result.details == {} for t in c.tests)


def test_daily_factors_are_constant_within_a_day(data: SeedData) -> None:
    per_day: dict[date, set[tuple[object, ...]]] = defaultdict(set)
    for c in data.checks:
        per_day[c.created_at.astimezone(TZ).date()].add(
            (c.caffeine, c.sleep_quality, c.stress, c.alcohol)
        )
    assert all(len(v) == 1 for v in per_day.values())
    factors = [next(iter(v)) for v in per_day.values()]
    assert {f[0] for f in factors} == {True, False}
    assert {f[3] for f in factors} == {True, False}
    assert all(1 <= int(str(f[1])) <= 5 and 1 <= int(str(f[2])) <= 5 for f in factors)
    assert any(int(str(f[1])) <= 2 for f in factors) and any(int(str(f[1])) >= 3 for f in factors)


def test_tremor_fields_follow_the_analysis_rules(data: SeedData) -> None:
    for c in data.checks:
        for t in c.tests[:2]:
            r = t.result
            assert r.strength_ms2 is not None and r.strength_ms2 > 0
            gate = RMS_MIN_MS2 if t.type == "rest" else POSTURE_RMS_MIN_MS2
            assert r.tremor_detected == (r.strength_ms2 >= gate)
            assert r.strength_score == pytest.approx(strength_to_score(r.strength_ms2))
            assert (r.peak_hz is None) == (not r.tremor_detected)
            assert r.valid_seconds is not None
        rest, posture = c.tests[0].result, c.tests[1].result
        assert rest.valid_seconds == 26.0
        assert posture.valid_seconds is not None and 22.0 <= posture.valid_seconds <= 30.0


def test_detection_tells_the_wearing_off_story(data: SeedData) -> None:
    early = [c.tests[0].result.tremor_detected for c in data.checks if _in(c, 1.0, 2.0)]
    late = [c.tests[0].result.tremor_detected for c in data.checks if _in(c, 3.5, 6.0)]
    assert early and not any(early)
    assert late and all(late)


def test_reach_and_tap_fields(data: SeedData) -> None:
    for c in data.checks:
        reach = c.tests[2].result
        assert reach.smoothness is not None and reach.smoothness > 0
        assert reach.wobble_ratio is not None and reach.wobble_ratio >= 1.0
        for t in c.tests[3:]:
            r = t.result
            assert r.taps_per_sec is not None and 2.5 < r.taps_per_sec < 5.0
            assert r.tap_amplitude is not None and r.tap_amplitude > 0
            assert r.amplitude_decrement is not None and -0.15 <= r.amplitude_decrement <= -0.05
            assert r.rhythm_cv is not None and 0.0 < r.rhythm_cv < 0.3
            assert r.strength_ms2 is None and r.valid_seconds is None


def test_wearing_off_pattern(data: SeedData) -> None:
    late = [_rest(c) for c in data.checks if _in(c, 3.0, 5.0)]
    early = [_rest(c) for c in data.checks if _in(c, 0.5, 1.5)]
    assert len(late) >= 5 and len(early) >= 5
    assert mean(late) > 2 * mean(early)


def test_caffeine_effect(data: SeedData) -> None:
    bins: dict[int, dict[bool, list[float]]] = defaultdict(lambda: {True: [], False: []})
    for c in data.checks:
        h = _hours(c)
        if h is None or h >= 6.0 or c.caffeine is None:
            continue
        bins[int(h // 0.5)][c.caffeine].append(_rest(c))
    weighted = [
        (min(len(g[True]), len(g[False])), mean(g[True]) / mean(g[False]))
        for g in bins.values()
        if g[True] and g[False]
    ]
    ratio = sum(w * r for w, r in weighted) / sum(w for w, _ in weighted)
    assert 1.12 <= ratio <= 1.30


def test_peak_hz_range(data: SeedData) -> None:
    peaks = [t.result.peak_hz for c in data.checks for t in c.tests if t.result.peak_hz is not None]
    assert len(peaks) >= 10
    assert all(4.5 <= p <= 5.5 for p in peaks)


def test_tap_faster_when_medicated(data: SeedData) -> None:
    def taps(c: SeedCheck) -> float:
        return mean(float(t.result.taps_per_sec or 0.0) for t in c.tests if t.type == "tap")

    medicated = [taps(c) for c in data.checks if _in(c, 1.0, 2.5)]
    wearing_off = [taps(c) for c in data.checks if not _in(c, 0.0, 3.5)]
    assert medicated and wearing_off
    assert mean(medicated) > mean(wearing_off) + 0.2


def test_local_timezone_default() -> None:
    data: SeedData = generate(seed=1, days=3, end=END)
    for d in data.doses:
        local = d.taken_at.astimezone()
        assert time(7, 50) <= local.time() <= time(18, 10)
    assert len({d.taken_at.astimezone().date() for d in data.doses}) == 3
    assert data.doses[0].taken_at.tzinfo is UTC
