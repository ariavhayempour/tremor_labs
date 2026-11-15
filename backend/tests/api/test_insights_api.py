import math
import sqlite3
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.fakes import FakeClock, QuietSource
from tremorlab import seeding
from tremorlab.analysis import insights
from tremorlab.analysis.insights import Bin, DayPoint, Obs, ProfileRow
from tremorlab.config import Config
from tremorlab.db import queries as q
from tremorlab.db.models import Hand, ResultRow, TestStatus, TestType
from tremorlab.db.seed_writer import write
from tremorlab.main import create_app

TZ = timezone(timedelta(hours=-8))
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=TZ)
TODAY = NOW.date()

Spec = tuple[TestType, Hand, TestStatus, ResultRow | None]


@dataclass
class Calls:
    args: dict[str, list[tuple[Any, ...]]] = field(default_factory=dict)

    def record(self, name: str, *args: Any) -> None:
        self.args.setdefault(name, []).append(args)


@pytest.fixture
def client(config: Config) -> Iterator[TestClient]:
    app = create_app(config, source=QuietSource(), clock=FakeClock(NOW.timestamp()))
    app.state.tz = TZ
    with TestClient(app) as c:
        yield c


def conn_of(client: TestClient) -> sqlite3.Connection:
    conn: sqlite3.Connection = client.app.state.conn  # type: ignore[attr-defined]
    return conn


def rest(strength: float, score: float = 40.0) -> ResultRow:
    return ResultRow(strength_ms2=strength, strength_score=score, peak_hz=5.0)


def add_check(
    conn: sqlite3.Connection,
    at: datetime,
    tests: Sequence[Spec] = (),
    *,
    minutes: float | None = 90.0,
) -> int:
    check_id = q.insert_check(
        conn,
        created_at=at,
        minutes_since_dose=minutes,
        notes=None,
        dose_id=None,
    )
    for i, (kind, hand, status, result) in enumerate(tests):
        test_id = q.insert_test(
            conn, check_id=check_id, type=kind, hand=hand, started_at=at + timedelta(minutes=i)
        )
        if result is not None:
            q.insert_result(conn, test_id, result)
        q.finish_test(conn, test_id, ended_at=at + timedelta(minutes=i, seconds=30), status=status)
    return check_id


def obs(at: datetime, kind: str, metric: float, **ctx: Any) -> Obs:
    defaults: dict[str, Any] = {"minutes_since_dose": 90.0}
    return Obs(created_at=at.astimezone(UTC), test_type=kind, metric=metric, **defaults | ctx)


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Calls:
    """Fake insight functions that record their inputs and return fixed rows."""
    c = Calls()

    def dose_response(o: Sequence[Obs]) -> list[Bin]:
        c.record("dose_response", list(o))
        return [Bin(0.0, 0.1, 3), Bin(0.5, math.nan, 0), Bin(3.0, 0.3, 4)]

    def returns_after_h(bins: Sequence[Bin], median: float) -> float | None:
        c.record("returns_after_h", list(bins), median)
        return 2.5

    def profile(o: Sequence[Obs], now: datetime) -> list[ProfileRow]:
        c.record("profile", list(o), now)
        return [
            ProfileRow("reach", 3.0, 1, None, 0),
            ProfileRow("rest", 40.0, 2, 45.0, 1),
            ProfileRow("posture", None, 0, 7.0, 0),
        ]

    def daily_timeline(o: Sequence[Obs], tz: tzinfo) -> list[DayPoint]:
        c.record("daily_timeline", list(o), tz)
        return [DayPoint(TODAY.isoformat(), 0.2, 1), DayPoint("2026-11-13", None, 0)]

    def streak_days(dates: Sequence[date], today: date) -> int:
        c.record("streak_days", list(dates), today)
        return 3

    for fn in (dose_response, returns_after_h, profile, daily_timeline):
        monkeypatch.setattr(insights, fn.__name__, fn)
    monkeypatch.setattr(insights, "streak_days", streak_days)
    return c


def get(client: TestClient, path: str, **params: Any) -> Any:
    r = client.get(f"/api/insights/{path}", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_dose_response_passes_rest_strengths_in_window(client: TestClient, calls: Calls) -> None:
    conn = conn_of(client)
    at = NOW - timedelta(days=1)
    add_check(
        conn,
        at,
        [
            ("rest", "right", "failed", None),
            ("rest", "right", "done", rest(0.2)),
            ("posture", "right", "done", rest(0.14)),
            ("tap", "right", "done", ResultRow(taps_per_sec=4.0)),
        ],
    )
    later = NOW - timedelta(hours=2)
    add_check(conn, later, [("rest", "left", "done", rest(0.4))], minutes=None)
    add_check(conn, NOW - timedelta(days=20), [("rest", "right", "done", rest(0.9))])
    dose_in = q.insert_dose(conn, NOW - timedelta(hours=3))
    q.insert_dose(conn, NOW - timedelta(days=20))

    body = get(client, "dose-response")

    assert calls.args["dose_response"] == [
        ([obs(at, "rest", 0.2), obs(later, "rest", 0.4, minutes_since_dose=None)],)
    ]
    ((bins, median),) = calls.args["returns_after_h"]
    assert median == pytest.approx(0.3) and len(bins) == 3
    assert body["bins"] == [
        {"start_h": 0.0, "mean": 0.1, "count": 3},
        {"start_h": 3.0, "mean": 0.3, "count": 4},
    ]
    assert body["returns_after_h"] == 2.5
    assert [d["id"] for d in body["doses"]] == [dose_in]
    assert set(body["doses"][0]) == {"id", "taken_at", "label"}


def test_retried_rest_uses_the_latest_done_take(client: TestClient, calls: Calls) -> None:
    at = NOW - timedelta(hours=5)
    add_check(
        conn_of(client),
        at,
        [("rest", "right", "done", rest(0.5)), ("rest", "right", "done", rest(0.25))],
    )
    get(client, "dose-response")
    assert calls.args["dose_response"] == [([obs(at, "rest", 0.25)],)]


def test_window_is_local_calendar_days_ending_now(client: TestClient, calls: Calls) -> None:
    conn = conn_of(client)
    first_day = datetime.combine(TODAY - timedelta(days=13), datetime.min.time(), tzinfo=TZ)
    inside = first_day + timedelta(minutes=30)
    add_check(conn, inside, [("rest", "right", "done", rest(0.1))])
    add_check(conn, first_day - timedelta(minutes=30), [("rest", "right", "done", rest(0.2))])
    add_check(conn, NOW + timedelta(minutes=5), [("rest", "right", "done", rest(0.3))])

    get(client, "dose-response")
    get(client, "dose-response", days=1)

    first, one_day = calls.args["dose_response"]
    assert first == ([obs(inside, "rest", 0.1)],)
    assert one_day == ([],)


def test_dose_response_without_rest_data(client: TestClient, calls: Calls) -> None:
    body = get(client, "dose-response")
    assert "returns_after_h" not in calls.args
    assert body["returns_after_h"] is None and body["doses"] == []


@pytest.mark.parametrize("days", [0, 366, "x"])
def test_days_out_of_range_is_422(client: TestClient, days: object) -> None:
    for path in ("dose-response", "profile", "summary"):
        r = client.get(f"/api/insights/{path}", params={"days": days})
        assert r.status_code == 422 and r.json()["error"] == "validation_error"


def test_profile_uses_card_metrics_in_card_order(client: TestClient, calls: Calls) -> None:
    at = NOW - timedelta(days=3)
    add_check(
        conn_of(client),
        at,
        [
            ("rest", "right", "done", rest(0.2, score=41.0)),
            ("posture", "right", "done", rest(0.1, score=22.0)),
            ("reach", "right", "done", ResultRow(smoothness=3.5)),
            ("reach", "right", "failed", None),
            ("tap", "left", "done", ResultRow(taps_per_sec=3.0)),
            ("tap", "right", "done", ResultRow(taps_per_sec=5.0)),
        ],
    )
    body = get(client, "profile")
    ((sent, now),) = calls.args["profile"]
    assert sent == [
        obs(at, "rest", 41.0),
        obs(at, "posture", 22.0),
        obs(at, "reach", 3.5),
        obs(at, "tap", 4.0),
    ]
    assert now == NOW.astimezone(UTC)
    assert [row["test_type"] for row in body] == ["rest", "posture", "reach", "tap"]
    assert body[0] == {
        "test_type": "rest",
        "first_week": 40.0,
        "first_n": 2,
        "current": 45.0,
        "current_n": 1,
    }
    assert body[1]["current"] is None  # a zero count always reports null
    assert body[3] == {
        "test_type": "tap",
        "first_week": None,
        "first_n": 0,
        "current": None,
        "current_n": 0,
    }


def test_summary_counts_streak_and_fills_daily(client: TestClient, calls: Calls) -> None:
    conn = conn_of(client)
    yesterday = NOW - timedelta(days=1)
    add_check(conn, yesterday, [("rest", "right", "done", rest(0.2))])
    add_check(conn, NOW - timedelta(hours=1), [("tap", "left", "done", ResultRow(taps_per_sec=4))])
    add_check(conn, NOW - timedelta(hours=2), [("rest", "right", "failed", None)])
    add_check(conn, NOW - timedelta(hours=3))
    old = NOW - timedelta(days=30)
    add_check(conn, old, [("posture", "right", "done", rest(0.1))])
    late_evening_utc = datetime(2026, 11, 14, 6, 0, tzinfo=UTC)  # 22:00 on Nov 13 at UTC-8
    add_check(conn, late_evening_utc, [("reach", "right", "done", ResultRow(smoothness=3))])

    body = get(client, "summary", days=3)

    assert body["checks_completed"] == 3
    ((dates, today),) = calls.args["streak_days"]
    assert today == TODAY
    assert dates == [old.date(), date(2026, 11, 13), TODAY]
    assert body["streak_days"] == 3
    ((sent, tz),) = calls.args["daily_timeline"]
    assert sent == [obs(yesterday, "rest", 0.2)] and tz is TZ
    assert body["daily"] == [
        {"date": "2026-11-12", "mean_rest": None, "count": 0},
        {"date": "2026-11-13", "mean_rest": None, "count": 0},
        {"date": "2026-11-14", "mean_rest": 0.2, "count": 1},
    ]
    assert body["returns_after_h"] == 2.5


def test_summary_defaults_to_fourteen_days(client: TestClient, calls: Calls) -> None:
    daily = get(client, "summary")["daily"]
    assert len(daily) == 14
    assert daily[0]["date"] == (TODAY - timedelta(days=13)).isoformat()
    assert daily[-1]["date"] == TODAY.isoformat()


@pytest.fixture
def seeded(client: TestClient) -> TestClient:
    """The real generator through yesterday, plus today's replay check 10 min before NOW."""
    end = TODAY - timedelta(days=1)
    data = seeding.generate(seed=42, days=14, end=end, tz=TZ)
    write(conn_of(client), data, replay_at=NOW - timedelta(minutes=10))
    return client


@pytest.mark.integration
def test_seeded_dose_response_shows_wearing_off(seeded: TestClient) -> None:
    body = get(seeded, "dose-response")
    assert 2.0 <= body["returns_after_h"] <= 4.0
    assert all(b["count"] > 0 and 0.0 <= b["start_h"] < 6.0 for b in body["bins"])
    assert len(body["doses"]) >= 36


@pytest.mark.integration
def test_seeded_summary_and_profile(seeded: TestClient) -> None:
    body = get(seeded, "summary")
    assert 40 <= body["checks_completed"] <= 57
    assert body["streak_days"] == 15 and len(body["daily"]) == 14
    assert body["daily"][-1]["count"] == 1  # today holds only the replay check
    profile = get(seeded, "profile")
    assert [row["test_type"] for row in profile] == ["rest", "posture", "reach", "tap"]
    assert all(row["first_n"] > 0 for row in profile)
