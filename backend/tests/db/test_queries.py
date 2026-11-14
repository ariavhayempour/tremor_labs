import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tremorlab.db import queries as q
from tremorlab.db.connection import connect
from tremorlab.db.models import CheckRow, DoseRow, ResultRow

T0 = datetime(2026, 11, 14, 15, 0, 0, tzinfo=UTC)


def add_check(conn: sqlite3.Connection, at: datetime = T0, **kw: object) -> int:
    fields: dict[str, object] = {
        "created_at": at,
        "minutes_since_dose": None,
        "caffeine": None,
        "sleep_quality": None,
        "stress": None,
        "alcohol": None,
        "notes": None,
        "dose_id": None,
    }
    fields.update(kw)
    return q.insert_check(conn, **fields)  # type: ignore[arg-type]


def test_connect_creates_parent_dirs_and_applies_schema(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "t.db"
    conn = connect(path)
    assert path.exists()
    assert conn.row_factory is sqlite3.Row
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "tests" in tables
    conn.close()
    connect(path).close()  # reopening an existing DB is fine


def test_connect_memory() -> None:
    conn = connect(":memory:")
    assert conn.execute("SELECT count(*) FROM checks").fetchone()[0] == 0


def test_check_roundtrip(mem_conn: sqlite3.Connection) -> None:
    dose = q.insert_dose(mem_conn, T0 - timedelta(hours=2))
    cid = add_check(
        mem_conn,
        minutes_since_dose=120.0,
        caffeine=True,
        sleep_quality=4,
        stress=2,
        alcohol=False,
        notes="ok",
        dose_id=dose,
    )
    row = q.get_check(mem_conn, cid)
    assert row == CheckRow(cid, T0, 120.0, True, 4, 2, False, "ok", dose)
    assert row.created_at.tzinfo is not None and row.created_at.utcoffset() == timedelta(0)
    assert q.get_check(mem_conn, 999) is None


def test_check_nullable_fields_roundtrip(mem_conn: sqlite3.Connection) -> None:
    cid = add_check(mem_conn)
    row = q.get_check(mem_conn, cid)
    assert row is not None and row.caffeine is None and row.alcohol is None


def test_non_utc_input_is_stored_as_utc(mem_conn: sqlite3.Connection) -> None:
    plus2 = timezone(timedelta(hours=2))
    cid = add_check(mem_conn, at=datetime(2026, 11, 14, 17, 0, tzinfo=plus2))
    row = q.get_check(mem_conn, cid)
    assert row is not None and row.created_at == T0 and row.created_at.tzinfo == UTC
    raw = mem_conn.execute("SELECT created_at FROM checks").fetchone()[0]
    assert raw.endswith("+00:00")


def test_list_checks_range_inclusive_and_chronological(mem_conn: sqlite3.Connection) -> None:
    ids = [add_check(mem_conn, at=T0 + timedelta(hours=h)) for h in (2, 0, 1, 3)]
    assert [c.id for c in q.list_checks(mem_conn, None, None)] == [ids[1], ids[2], ids[0], ids[3]]
    ranged = q.list_checks(mem_conn, T0 + timedelta(hours=1), T0 + timedelta(hours=2))
    assert [c.id for c in ranged] == [ids[2], ids[0]]


def test_test_roundtrip_and_finish(mem_conn: sqlite3.Connection) -> None:
    cid = add_check(mem_conn)
    tid = q.insert_test(mem_conn, check_id=cid, type="reach", hand="right", started_at=T0)
    [row] = q.tests_for_check(mem_conn, cid)
    assert (row.id, row.type, row.hand, row.status, row.ended_at) == (
        tid,
        "reach",
        "right",
        "recording",
        None,
    )
    assert row.markers == [] and row.started_at == T0
    end = T0 + timedelta(seconds=30)
    q.finish_test(mem_conn, tid, ended_at=end, status="done", markers=[1.5, 2.25])
    [row] = q.tests_for_check(mem_conn, cid)
    assert row.status == "done" and row.ended_at == end and row.markers == [1.5, 2.25]
    assert row.fail_reason is None


def test_tests_for_check_in_start_order(mem_conn: sqlite3.Connection) -> None:
    cid = add_check(mem_conn)
    a = q.insert_test(mem_conn, check_id=cid, type="rest", hand="right", started_at=T0)
    b = q.insert_test(
        mem_conn, check_id=cid, type="posture", hand="right", started_at=T0 + timedelta(seconds=40)
    )
    assert [t.id for t in q.tests_for_check(mem_conn, cid)] == [a, b]


def test_fail_stale_recordings_marks_interrupted(mem_conn: sqlite3.Connection) -> None:
    cid = add_check(mem_conn)
    old = q.insert_test(mem_conn, check_id=cid, type="rest", hand="right", started_at=T0)
    young = q.insert_test(
        mem_conn, check_id=cid, type="posture", hand="right", started_at=T0 + timedelta(minutes=5)
    )
    done = q.insert_test(mem_conn, check_id=cid, type="tap", hand="left", started_at=T0)
    q.finish_test(mem_conn, done, ended_at=T0, status="done")

    assert q.fail_stale_recordings(mem_conn, older_than=T0 + timedelta(minutes=1)) == 1
    by_id = {t.id: t for t in q.tests_for_check(mem_conn, cid)}
    assert (by_id[old].status, by_id[old].fail_reason) == ("failed", "interrupted")
    assert by_id[old].ended_at is not None
    assert by_id[young].status == "recording"
    assert by_id[done].status == "done"

    assert q.fail_stale_recordings(mem_conn) == 1
    young_row = q.get_test(mem_conn, young)
    assert young_row is not None and young_row.fail_reason == "interrupted"
    assert q.fail_stale_recordings(mem_conn) == 0


def test_get_test(mem_conn: sqlite3.Connection) -> None:
    cid = add_check(mem_conn)
    tid = q.insert_test(mem_conn, check_id=cid, type="tap", hand="left", started_at=T0)
    row = q.get_test(mem_conn, tid)
    assert row is not None and row.type == "tap" and row.status == "recording"
    assert q.get_test(mem_conn, 999) is None


def test_result_roundtrip(mem_conn: sqlite3.Connection) -> None:
    cid = add_check(mem_conn)
    tid = q.insert_test(mem_conn, check_id=cid, type="rest", hand="right", started_at=T0)
    r = ResultRow(
        peak_hz=5.02,
        strength_ms2=0.21,
        strength_score=55.0,
        tremor_detected=True,
        valid_seconds=26.0,
        details={"freqs": [0.0, 0.25], "psd": [0.001, 0.002]},
    )
    q.insert_result(mem_conn, tid, r)
    assert q.get_result(mem_conn, tid) == r
    assert q.get_result(mem_conn, 999) is None


def test_result_with_no_tremor_keeps_false_and_none(mem_conn: sqlite3.Connection) -> None:
    cid = add_check(mem_conn)
    tid = q.insert_test(mem_conn, check_id=cid, type="rest", hand="right", started_at=T0)
    q.insert_result(mem_conn, tid, ResultRow(peak_hz=None, tremor_detected=False))
    got = q.get_result(mem_conn, tid)
    assert got is not None and got.tremor_detected is False and got.peak_hz is None
    assert got.details == {}


def test_raw_roundtrip_in_insert_order(mem_conn: sqlite3.Connection) -> None:
    cid = add_check(mem_conn)
    tid = q.insert_test(mem_conn, check_id=cid, type="rest", hand="right", started_at=T0)
    imu = {"type": "imu", "t0": 1.0, "fs": 100.0, "samples": [[0.0] * 6]}
    tof = {"type": "tof", "t0": 1.0, "fs": 40.0, "samples_mm": [200.0]}
    q.insert_raw(mem_conn, tid, "imu", imu)
    q.insert_raw(mem_conn, tid, "tof", tof)
    assert q.raw_for_test(mem_conn, tid) == [("imu", imu), ("tof", tof)]
    assert q.raw_for_test(mem_conn, 999) == []


def test_dose_near_window_is_30_min(mem_conn: sqlite3.Connection) -> None:
    did = q.insert_dose(mem_conn, T0, "morning")
    found = q.dose_near(mem_conn, T0 + timedelta(minutes=29))
    assert found == DoseRow(did, T0, "morning")
    assert q.dose_near(mem_conn, T0 - timedelta(minutes=29)) == found
    assert q.dose_near(mem_conn, T0 + timedelta(minutes=31)) is None
    assert q.dose_near(mem_conn, T0 - timedelta(minutes=31)) is None


def test_dose_near_picks_closest(mem_conn: sqlite3.Connection) -> None:
    q.insert_dose(mem_conn, T0)
    later = q.insert_dose(mem_conn, T0 + timedelta(minutes=40))
    found = q.dose_near(mem_conn, T0 + timedelta(minutes=25))
    assert found is not None and found.id == later


def test_latest_dose_at_or_before_ignores_future(mem_conn: sqlite3.Connection) -> None:
    assert q.latest_dose_at_or_before(mem_conn, T0) is None
    early = q.insert_dose(mem_conn, T0 - timedelta(hours=3))
    exact = q.insert_dose(mem_conn, T0)
    q.insert_dose(mem_conn, T0 + timedelta(minutes=1))
    found = q.latest_dose_at_or_before(mem_conn, T0)
    assert found is not None and found.id == exact
    found = q.latest_dose_at_or_before(mem_conn, T0 - timedelta(minutes=1))
    assert found is not None and found.id == early


def test_list_doses_oldest_first_inclusive(mem_conn: sqlite3.Connection) -> None:
    ids = [q.insert_dose(mem_conn, T0 + timedelta(hours=h)) for h in (5, 0, 2)]
    assert [d.id for d in q.list_doses(mem_conn, None, None)] == [ids[1], ids[2], ids[0]]
    ranged = q.list_doses(mem_conn, T0, T0 + timedelta(hours=2))
    assert [d.id for d in ranged] == [ids[1], ids[2]]


def test_settings_roundtrip_json(mem_conn: sqlite3.Connection) -> None:
    assert q.get_settings(mem_conn) == {}
    out = q.put_settings(mem_conn, {"dose_times": ["08:00", "13:00"], "posture_band": [170, 230]})
    assert out == {"dose_times": ["08:00", "13:00"], "posture_band": [170, 230]}
    out = q.put_settings(mem_conn, {"posture_band": None, "tested_hand": "left"})
    assert out == {"dose_times": ["08:00", "13:00"], "posture_band": None, "tested_hand": "left"}
    assert q.get_settings(mem_conn) == out


def _done_rest(conn: sqlite3.Connection, at: datetime, score: float) -> int:
    cid = add_check(conn, at=at)
    tid = q.insert_test(conn, check_id=cid, type="rest", hand="right", started_at=at)
    q.finish_test(conn, tid, ended_at=at, status="done")
    q.insert_result(conn, tid, ResultRow(strength_score=score))
    return cid


def test_results_history_only_done_and_ordered(mem_conn: sqlite3.Connection) -> None:
    c1 = _done_rest(mem_conn, T0, 10.0)
    c2 = _done_rest(mem_conn, T0 + timedelta(hours=1), 20.0)
    c3 = _done_rest(mem_conn, T0 + timedelta(hours=2), 30.0)
    failed_check = add_check(mem_conn, at=T0 + timedelta(minutes=30))
    ft = q.insert_test(mem_conn, check_id=failed_check, type="rest", hand="right", started_at=T0)
    q.finish_test(mem_conn, ft, ended_at=T0, status="failed", fail_reason="sensor_disconnected")
    _done_rest(mem_conn, T0 + timedelta(hours=5), 50.0)  # after `before`
    posture_check = add_check(mem_conn, at=T0)
    pt = q.insert_test(
        mem_conn, check_id=posture_check, type="posture", hand="right", started_at=T0
    )
    q.finish_test(mem_conn, pt, ended_at=T0, status="done")
    q.insert_result(mem_conn, pt, ResultRow(strength_score=99.0))

    before = T0 + timedelta(hours=3)
    history = q.results_history(mem_conn, "rest", before)
    assert [c.id for c, _ in history] == [c3, c2, c1]
    assert [r.strength_score for _, r in history] == [30.0, 20.0, 10.0]
    assert [c.id for c, _ in q.results_history(mem_conn, "rest", before, limit=2)] == [c3, c2]


def test_foreign_key_enforced(mem_conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        q.insert_test(mem_conn, check_id=999, type="rest", hand="right", started_at=T0)
    conn = connect(":memory:")
    with pytest.raises(sqlite3.IntegrityError):
        q.insert_result(conn, 999, ResultRow())
