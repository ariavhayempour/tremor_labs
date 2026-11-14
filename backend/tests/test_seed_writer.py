import importlib.util
import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

from tremorlab import seeding
from tremorlab.config import load_config
from tremorlab.db import queries as q
from tremorlab.db.connection import connect
from tremorlab.db.models import CheckRow, Hand, ResultRow, TestType
from tremorlab.db.seed_writer import REPLAY_AGE, write
from tremorlab.seeding import SeedCheck, SeedData, SeedDose, SeedTest
from tremorlab.sources.replay import make_replay_source

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"
DAY0 = datetime(2026, 11, 13, 7, 0, tzinfo=UTC)
REPLAY_AT = DAY0 + timedelta(days=1, hours=8)  # after every seeded check and dose
REPLAY_TYPES: tuple[TestType, ...] = ("rest", "posture", "reach")


def load_seed_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_script", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def seed_tests(at: datetime, strength: float) -> list[SeedTest]:
    def t(kind: TestType, hand: Hand, minute: int, result: ResultRow) -> SeedTest:
        return SeedTest(kind, hand, at + timedelta(minutes=minute), result)

    tremor = ResultRow(
        peak_hz=5.0, strength_ms2=strength, strength_score=40.0, tremor_detected=True
    )
    return [
        t("rest", "right", 1, tremor),
        t("posture", "right", 2, ResultRow(strength_ms2=0.7 * strength, strength_score=30.0)),
        t("reach", "right", 3, ResultRow(smoothness=3.0, wobble_ratio=1.2)),
        t("tap", "left", 4, ResultRow(taps_per_sec=4.0, rhythm_cv=0.1)),
        t("tap", "right", 5, ResultRow(taps_per_sec=3.8, rhythm_cv=0.12)),
    ]


def small_data(*, bad_sleep: bool = False) -> SeedData:
    """Two days, two doses a day; the first check precedes every dose."""
    doses = [
        SeedDose(DAY0 + timedelta(hours=1)),
        SeedDose(DAY0 + timedelta(hours=6), "noon"),
        SeedDose(DAY0 + timedelta(days=1, hours=1)),
        SeedDose(DAY0 + timedelta(days=1, hours=6)),
    ]
    checks = []
    for i, (hours, dose_index) in enumerate([(0.5, None), (3.0, 0), (8.0, 1), (27.0, 2)]):
        at = DAY0 + timedelta(hours=hours)
        minutes = (
            None if dose_index is None else (at - doses[dose_index].taken_at) / timedelta(minutes=1)
        )
        checks.append(
            SeedCheck(
                created_at=at,
                minutes_since_dose=minutes,
                caffeine=i % 2 == 0,
                sleep_quality=9 if bad_sleep and i == 3 else 2 + i,
                stress=1 + i,
                alcohol=i == 3,
                dose_index=dose_index,
                tests=seed_tests(at, 0.1 + 0.05 * i),
            )
        )
    return SeedData(doses=doses, checks=checks)


@pytest.fixture(scope="module")
def written() -> Iterator[sqlite3.Connection]:
    conn = connect(":memory:")
    write(conn, small_data(), replay_at=REPLAY_AT)
    yield conn
    conn.close()


def seeded_checks(conn: sqlite3.Connection) -> list[CheckRow]:
    return q.list_checks(conn, None, None)[:-1]


def replay_check(conn: sqlite3.Connection) -> CheckRow:
    return q.list_checks(conn, None, None)[-1]


def test_doses_round_trip(written: sqlite3.Connection) -> None:
    doses = q.list_doses(written, None, None)
    assert [(d.taken_at, d.label) for d in doses] == [
        (d.taken_at, d.label) for d in small_data().doses
    ]


def test_checks_round_trip(written: sqlite3.Connection) -> None:
    data = small_data()
    rows = seeded_checks(written)
    assert len(rows) == len(data.checks)
    for row, c in zip(rows, data.checks, strict=True):
        assert (row.created_at, row.caffeine, row.sleep_quality, row.stress, row.alcohol) == (
            c.created_at,
            c.caffeine,
            c.sleep_quality,
            c.stress,
            c.alcohol,
        )
        assert row.minutes_since_dose == pytest.approx(c.minutes_since_dose)
        assert row.notes is None


def test_dose_id_resolved_from_dose_index(written: sqlite3.Connection) -> None:
    doses = q.list_doses(written, None, None)
    for row, c in zip(seeded_checks(written), small_data().checks, strict=True):
        expected = None if c.dose_index is None else doses[c.dose_index].id
        assert row.dose_id == expected


def test_tests_and_results_round_trip(written: sqlite3.Connection) -> None:
    for row, c in zip(seeded_checks(written), small_data().checks, strict=True):
        tests = q.tests_for_check(written, row.id)
        assert [(t.type, t.hand, t.started_at) for t in tests] == [
            (s.type, s.hand, s.started_at) for s in c.tests
        ]
        for t, s in zip(tests, c.tests, strict=True):
            assert t.status == "done" and t.fail_reason is None
            assert t.ended_at is not None and t.ended_at > t.started_at
            assert q.get_result(written, t.id) == s.result
            assert q.raw_for_test(written, t.id) == []


def test_bad_row_rolls_back_everything(tmp_path: Path) -> None:
    conn = connect(tmp_path / "x.db")
    with pytest.raises(sqlite3.IntegrityError):
        write(conn, small_data(bad_sleep=True), replay_at=REPLAY_AT)
    assert q.list_doses(conn, None, None) == []
    assert q.list_checks(conn, None, None) == []
    q.insert_dose(conn, DAY0)  # the connection still commits normally afterwards
    conn.close()
    assert len(q.list_doses(connect(tmp_path / "x.db"), None, None)) == 1


def test_replay_check_is_newest_with_dose_fields(written: sqlite3.Connection) -> None:
    data = small_data()
    row = replay_check(written)
    last = data.checks[-1]
    assert row.created_at == REPLAY_AT
    dose = q.latest_dose_at_or_before(written, row.created_at)
    assert dose is not None and row.dose_id == dose.id
    assert row.minutes_since_dose == pytest.approx(
        (row.created_at - dose.taken_at).total_seconds() / 60
    )
    assert (row.caffeine, row.sleep_quality, row.stress, row.alcohol) == (
        last.caffeine,
        last.sleep_quality,
        last.stress,
        last.alcohol,
    )


def test_replay_check_has_raw_rest_posture_reach(written: sqlite3.Connection) -> None:
    row = replay_check(written)
    tests = q.tests_for_check(written, row.id)
    assert [t.type for t in tests] == list(REPLAY_TYPES)
    assert all(t.status == "done" and t.started_at > row.created_at for t in tests)
    for t in tests:
        raw = q.raw_for_test(written, t.id)
        assert {s for s, _ in raw} == {"imu", "tof"}
        tof = next(p for s, p in raw if s == "tof")
        assert {"type", "t0", "fs", "samples_mm", "t"} <= set(tof)
        assert len(tof["t"]) == len(tof["samples_mm"])
    assert q.latest_replayable_tests(written) == [t.id for t in tests]


def test_replay_check_durations(written: sqlite3.Connection) -> None:
    rest, posture, reach = q.tests_for_check(written, replay_check(written).id)
    for t, seconds in ((rest, 30), (posture, 30), (reach, 15)):
        assert t.ended_at is not None
        assert (t.ended_at - t.started_at).total_seconds() == pytest.approx(seconds, abs=0.5)
    assert len(reach.markers) == 3


def test_replay_check_results_come_from_real_analysis(written: sqlite3.Connection) -> None:
    rest, posture, reach = q.tests_for_check(written, replay_check(written).id)
    for t in (rest, posture):
        r = q.get_result(written, t.id)
        assert r is not None and r.tremor_detected is True
        assert r.peak_hz == pytest.approx(5.0, abs=0.3)
        assert r.valid_seconds is not None and r.valid_seconds >= 20
        assert r.details["freqs"]
    r = q.get_result(written, reach.id)
    assert r is not None and r.smoothness is not None
    assert len(r.details["attempts"]) == 3


def test_replay_check_is_deterministic(written: sqlite3.Connection) -> None:
    other = connect(":memory:")
    write(other, small_data(), replay_at=REPLAY_AT)

    def snapshot(conn: sqlite3.Connection) -> list[object]:
        tests = q.tests_for_check(conn, replay_check(conn).id)
        return [(t, q.get_result(conn, t.id), q.raw_for_test(conn, t.id)) for t in tests]

    assert snapshot(other) == snapshot(written)
    other.close()


def test_replay_seed_changes_samples() -> None:
    a, b = connect(":memory:"), connect(":memory:")
    write(a, small_data(), replay_seed=1, replay_at=REPLAY_AT)
    write(b, small_data(), replay_seed=2, replay_at=REPLAY_AT)
    rest_a = q.tests_for_check(a, replay_check(a).id)[0]
    rest_b = q.tests_for_check(b, replay_check(b).id)[0]
    assert q.raw_for_test(a, rest_a.id) != q.raw_for_test(b, rest_b.id)


def test_replay_check_defaults_to_ten_minutes_ago() -> None:
    conn = connect(":memory:")
    before = datetime.now(UTC) - REPLAY_AGE
    write(conn, small_data())
    after = datetime.now(UTC) - REPLAY_AGE
    assert timedelta(minutes=10) == REPLAY_AGE
    assert before <= replay_check(conn).created_at <= after


def test_replay_check_must_follow_seeded_checks() -> None:
    conn = connect(":memory:")
    with pytest.raises(ValueError, match="last seeded check"):
        write(conn, small_data(), replay_at=small_data().checks[-1].created_at)
    assert q.list_doses(conn, None, None) == []


def test_without_checks_replay_check_uses_latest_dose_before_it() -> None:
    conn = connect(":memory:")
    doses = small_data().doses
    write(conn, SeedData(doses=doses, checks=[]), replay_at=doses[2].taken_at + timedelta(hours=1))
    (row,) = q.list_checks(conn, None, None)
    assert row.dose_id == q.list_doses(conn, None, None)[2].id
    assert row.minutes_since_dose == pytest.approx(60.0)
    assert (row.caffeine, row.sleep_quality, row.stress, row.alcohol) == (None, None, None, None)


def test_replay_check_before_any_dose_has_null_dose_fields() -> None:
    conn = connect(":memory:")
    write(conn, SeedData(doses=small_data().doses, checks=[]), replay_at=DAY0)
    (row,) = q.list_checks(conn, None, None)
    assert row.dose_id is None and row.minutes_since_dose is None


def test_make_replay_source_starts_on_written_db(tmp_path: Path) -> None:
    config = load_config({"DB_PATH": str(tmp_path / "demo.db"), "SENSOR_SOURCE": "replay"})
    conn = connect(config.db_path)
    write(conn, small_data(), replay_at=REPLAY_AT)
    expected = [t.id for t in q.tests_for_check(conn, replay_check(conn).id)]
    conn.close()
    source = make_replay_source(config)
    assert source.test_ids == expected


def test_cli_writes_and_reset_replaces_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[int, int, date | None]] = []

    def fake_generate(seed: int = 42, days: int = 14, end: date | None = None) -> SeedData:
        calls.append((seed, days, end))
        return small_data()

    monkeypatch.setattr(seeding, "generate", fake_generate)
    cli = load_seed_script()
    db = tmp_path / "data" / "seed.db"
    assert cli.main(["--db", str(db), "--seed", "7", "--days", "3", "--end", "2026-11-13"]) == 0
    assert cli.main(["--db", str(db), "--reset"]) == 0
    assert calls == [(7, 3, date(2026, 11, 13)), (42, 14, date.today() - timedelta(days=1))]
    conn = connect(db)
    assert len(q.list_checks(conn, None, None)) == len(small_data().checks) + 1
    assert len(q.list_doses(conn, None, None)) == len(small_data().doses)
    conn.close()
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 2 and "4 checks" in out[-1] and "replay" in out[-1]


def test_cli_without_reset_appends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seeding, "generate", lambda **_: small_data())
    cli = load_seed_script()
    db = tmp_path / "seed.db"
    cli.main(["--db", str(db)])
    cli.main(["--db", str(db)])
    conn = connect(db)
    assert len(q.list_doses(conn, None, None)) == 2 * len(small_data().doses)
    conn.close()


@pytest.mark.integration
def test_cli_on_real_generator(tmp_path: Path) -> None:
    db = tmp_path / "seed.db"
    assert load_seed_script().main(["--db", str(db), "--reset"]) == 0
    conn = connect(db)
    checks = q.list_checks(conn, None, None)
    assert 42 <= len(checks) - 1 <= 56
    assert all(
        not q.raw_for_test(conn, t.id) for c in checks[:-1] for t in q.tests_for_check(conn, c.id)
    )
    replay = checks[-1]
    today = date.today()
    assert [c.id for c in checks if c.created_at.astimezone().date() == today] == [replay.id]
    assert replay.created_at < datetime.now(UTC) and replay.dose_id is not None
    assert len(q.latest_replayable_tests(conn)) == 3
    conn.close()
