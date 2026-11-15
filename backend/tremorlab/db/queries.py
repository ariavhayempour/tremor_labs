"""All SQL lives here. Every function takes the connection first; datetimes are UTC-aware."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from tremorlab.db.models import (
    CheckRow,
    DoseRow,
    FailReason,
    Hand,
    ResultRow,
    Sensor,
    TestRow,
    TestStatus,
    TestType,
)

DOSE_MATCH_MINUTES = 30.0

_CHECK_COLS = "id, created_at, minutes_since_dose, notes, dose_id"
_TEST_COLS = "id, check_id, type, hand, started_at, ended_at, status, fail_reason, markers_json"
_RESULT_FIELDS = (
    "peak_hz",
    "strength_ms2",
    "strength_score",
    "tremor_detected",
    "smoothness",
    "wobble_ratio",
    "taps_per_sec",
    "tap_amplitude",
    "amplitude_decrement",
    "rhythm_cv",
    "valid_seconds",
)


def _iso(dt: datetime) -> str:
    """Fixed-width ISO-8601 UTC, so string order is time order; naive input is taken as UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat(timespec="microseconds")


def _dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC)


def _opt_dt(s: str | None) -> datetime | None:
    return None if s is None else _dt(s)


def _opt_bool(v: int | None) -> bool | None:
    return None if v is None else bool(v)


def _db_bool(v: bool | None) -> int | None:
    return None if v is None else int(v)


def _range_clauses(
    column: str, start: datetime | None, end: datetime | None
) -> tuple[list[str], list[str]]:
    clauses: list[str] = []
    args: list[str] = []
    if start is not None:
        clauses.append(f"{column} >= ?")
        args.append(_iso(start))
    if end is not None:
        clauses.append(f"{column} <= ?")
        args.append(_iso(end))
    return clauses, args


def _range_sql(column: str, start: datetime | None, end: datetime | None) -> tuple[str, list[str]]:
    clauses, args = _range_clauses(column, start, end)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), args


def _check_row(r: sqlite3.Row) -> CheckRow:
    return CheckRow(
        id=r["id"],
        created_at=_dt(r["created_at"]),
        minutes_since_dose=r["minutes_since_dose"],
        notes=r["notes"],
        dose_id=r["dose_id"],
    )


def _test_row(r: sqlite3.Row) -> TestRow:
    return TestRow(
        id=r["id"],
        check_id=r["check_id"],
        type=cast(TestType, r["type"]),
        hand=cast(Hand, r["hand"]),
        started_at=_dt(r["started_at"]),
        ended_at=_opt_dt(r["ended_at"]),
        status=cast(TestStatus, r["status"]),
        fail_reason=cast(FailReason | None, r["fail_reason"]),
        markers=json.loads(r["markers_json"]) if r["markers_json"] else [],
    )


def _result_row(r: sqlite3.Row) -> ResultRow:
    values: dict[str, Any] = {f: r[f] for f in _RESULT_FIELDS}
    values["tremor_detected"] = _opt_bool(values["tremor_detected"])
    details = json.loads(r["details_json"]) if r["details_json"] else {}
    return ResultRow(**values, details=details)


def _dose_row(r: sqlite3.Row) -> DoseRow:
    return DoseRow(id=r["id"], taken_at=_dt(r["taken_at"]), label=r["label"])


def _insert(conn: sqlite3.Connection, sql: str, args: tuple[Any, ...]) -> int:
    with conn:
        cur = conn.execute(sql, args)
    assert cur.lastrowid is not None
    return cur.lastrowid


def insert_check(
    conn: sqlite3.Connection,
    *,
    created_at: datetime,
    minutes_since_dose: float | None,
    notes: str | None,
    dose_id: int | None,
) -> int:
    return _insert(
        conn,
        "INSERT INTO checks (created_at, minutes_since_dose, notes, dose_id) VALUES (?, ?, ?, ?)",
        (
            _iso(created_at),
            minutes_since_dose,
            notes,
            dose_id,
        ),
    )


def get_check(conn: sqlite3.Connection, check_id: int) -> CheckRow | None:
    r = conn.execute(f"SELECT {_CHECK_COLS} FROM checks WHERE id = ?", (check_id,)).fetchone()
    return None if r is None else _check_row(r)


def list_checks(
    conn: sqlite3.Connection, start: datetime | None, end: datetime | None
) -> list[CheckRow]:
    """Checks with start <= created_at <= end (either bound optional), oldest first."""
    where, args = _range_sql("created_at", start, end)
    rows = conn.execute(f"SELECT {_CHECK_COLS} FROM checks{where} ORDER BY created_at, id", args)
    return [_check_row(r) for r in rows]


def insert_test(
    conn: sqlite3.Connection, *, check_id: int, type: TestType, hand: Hand, started_at: datetime
) -> int:
    """New test row in status `recording`."""
    return _insert(
        conn,
        "INSERT INTO tests (check_id, type, hand, started_at, status)"
        " VALUES (?, ?, ?, ?, 'recording')",
        (check_id, type, hand, _iso(started_at)),
    )


def finish_test(
    conn: sqlite3.Connection,
    test_id: int,
    *,
    ended_at: datetime,
    status: TestStatus,
    fail_reason: FailReason | None = None,
    markers: list[float] | None = None,
) -> None:
    """Set the final status; markers None keeps any stored markers."""
    with conn:
        conn.execute(
            "UPDATE tests SET ended_at = ?, status = ?, fail_reason = ?,"
            " markers_json = COALESCE(?, markers_json) WHERE id = ?",
            (
                _iso(ended_at),
                status,
                fail_reason,
                None if markers is None else json.dumps(markers),
                test_id,
            ),
        )


def get_test(conn: sqlite3.Connection, test_id: int) -> TestRow | None:
    r = conn.execute(f"SELECT {_TEST_COLS} FROM tests WHERE id = ?", (test_id,)).fetchone()
    return None if r is None else _test_row(r)


def tests_for_check(conn: sqlite3.Connection, check_id: int) -> list[TestRow]:
    """Tests of one check in the order they were started."""
    rows = conn.execute(
        f"SELECT {_TEST_COLS} FROM tests WHERE check_id = ? ORDER BY started_at, id", (check_id,)
    )
    return [_test_row(r) for r in rows]


def fail_stale_recordings(conn: sqlite3.Connection, *, older_than: datetime | None = None) -> int:
    """Recording tests started before older_than (all if None) → failed/interrupted; count."""
    now = _iso(datetime.now(UTC))
    sql = (
        "UPDATE tests SET status = 'failed', fail_reason = 'interrupted',"
        " ended_at = COALESCE(ended_at, ?) WHERE status = 'recording'"
    )
    args: tuple[str, ...] = (now,)
    if older_than is not None:
        sql += " AND started_at < ?"
        args = (now, _iso(older_than))
    with conn:
        return conn.execute(sql, args).rowcount


def insert_result(conn: sqlite3.Connection, test_id: int, r: ResultRow) -> None:
    values = [getattr(r, f) for f in _RESULT_FIELDS]
    values[_RESULT_FIELDS.index("tremor_detected")] = _db_bool(r.tremor_detected)
    cols = ", ".join(_RESULT_FIELDS)
    marks = ", ".join("?" for _ in range(len(_RESULT_FIELDS) + 2))
    with conn:
        conn.execute(
            f"INSERT INTO results (test_id, {cols}, details_json) VALUES ({marks})",
            (test_id, *values, json.dumps(r.details)),
        )


def get_result(conn: sqlite3.Connection, test_id: int) -> ResultRow | None:
    cols = ", ".join(_RESULT_FIELDS)
    r = conn.execute(
        f"SELECT {cols}, details_json FROM results WHERE test_id = ?", (test_id,)
    ).fetchone()
    return None if r is None else _result_row(r)


def insert_raw(
    conn: sqlite3.Connection, test_id: int, sensor: Sensor, payload: dict[str, Any]
) -> None:
    with conn:
        conn.execute(
            "INSERT INTO raw_samples (test_id, sensor, payload_json) VALUES (?, ?, ?)",
            (test_id, sensor, json.dumps(payload)),
        )


def raw_for_test(conn: sqlite3.Connection, test_id: int) -> list[tuple[Sensor, dict[str, Any]]]:
    """Stored payloads in insert order."""
    rows = conn.execute(
        "SELECT sensor, payload_json FROM raw_samples WHERE test_id = ? ORDER BY id", (test_id,)
    )
    return [(cast(Sensor, r["sensor"]), json.loads(r["payload_json"])) for r in rows]


def insert_dose(conn: sqlite3.Connection, taken_at: datetime, label: str | None = None) -> int:
    return _insert(
        conn, "INSERT INTO doses (taken_at, label) VALUES (?, ?)", (_iso(taken_at), label)
    )


def dose_near(
    conn: sqlite3.Connection, t: datetime, minutes: float = DOSE_MATCH_MINUTES
) -> DoseRow | None:
    """The dose closest to t within ±minutes, or None."""
    window = timedelta(minutes=minutes)
    candidates = list_doses(conn, t - window, t + window)
    return min(candidates, key=lambda d: abs(d.taken_at - t), default=None)


def latest_dose_at_or_before(conn: sqlite3.Connection, t: datetime) -> DoseRow | None:
    r = conn.execute(
        "SELECT id, taken_at, label FROM doses WHERE taken_at <= ?"
        " ORDER BY taken_at DESC, id DESC LIMIT 1",
        (_iso(t),),
    ).fetchone()
    return None if r is None else _dose_row(r)


def list_doses(
    conn: sqlite3.Connection, start: datetime | None, end: datetime | None
) -> list[DoseRow]:
    """Doses with start <= taken_at <= end (either bound optional), oldest first."""
    where, args = _range_sql("taken_at", start, end)
    rows = conn.execute(f"SELECT id, taken_at, label FROM doses{where} ORDER BY taken_at, id", args)
    return [_dose_row(r) for r in rows]


def get_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    """Stored settings only (no defaults); values are decoded JSON."""
    return {
        r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT key, value FROM settings")
    }


def put_settings(conn: sqlite3.Connection, values: dict[str, Any]) -> dict[str, Any]:
    """Upsert each key (None is stored as JSON null); returns all stored settings."""
    with conn:
        conn.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(k, json.dumps(v)) for k, v in values.items()],
        )
    return get_settings(conn)


def results_history(
    conn: sqlite3.Connection, test_type: TestType, before: datetime, limit: int | None = None
) -> list[tuple[CheckRow, ResultRow]]:
    """Done tests of test_type from checks before `before`, newest first."""
    check_cols = ", ".join(f"c.{c.strip()}" for c in _CHECK_COLS.split(","))
    result_cols = ", ".join(f"r.{f}" for f in _RESULT_FIELDS)
    sql = (
        f"SELECT {check_cols}, {result_cols}, r.details_json FROM tests t"
        " JOIN checks c ON c.id = t.check_id JOIN results r ON r.test_id = t.id"
        " WHERE t.type = ? AND t.status = 'done' AND c.created_at < ?"
        " ORDER BY c.created_at DESC, t.id DESC"
    )
    args: list[Any] = [test_type, _iso(before)]
    if limit is not None:
        sql += " LIMIT ?"
        args.append(limit)
    return [(_check_row(r), _result_row(r)) for r in conn.execute(sql, args)]


def latest_replayable_tests(
    conn: sqlite3.Connection, types: tuple[TestType, ...] = ("rest", "posture", "reach")
) -> list[int]:
    """Per type, the latest done test with raw samples from the newest check having all types."""
    marks = ", ".join("?" for _ in types)
    rows = conn.execute(
        "SELECT t.check_id, t.type, MAX(t.id) AS test_id FROM tests t"
        " JOIN checks c ON c.id = t.check_id"
        f" WHERE t.status = 'done' AND t.type IN ({marks})"
        " AND EXISTS (SELECT 1 FROM raw_samples r WHERE r.test_id = t.id)"
        " GROUP BY t.check_id, t.type ORDER BY c.created_at DESC, c.id DESC",
        types,
    )
    per_check: dict[int, dict[str, int]] = {}
    for r in rows:
        per_check.setdefault(r["check_id"], {})[r["type"]] = r["test_id"]
    for found in per_check.values():
        if all(kind in found for kind in types):
            return [found[kind] for kind in types]
    return []


def done_metrics(
    conn: sqlite3.Connection, start: datetime | None, end: datetime | None
) -> list[tuple[CheckRow, TestRow, ResultRow]]:
    """Done tests with a result, checks start <= created_at <= end; details are left empty."""
    clauses, args = _range_clauses("c.created_at", start, end)
    check_cols = ", ".join(f"c.{c.strip()}" for c in _CHECK_COLS.split(","))
    result_cols = ", ".join(f"r.{f}" for f in _RESULT_FIELDS)
    sql = (
        f"SELECT {check_cols}, t.id AS test_id, t.type AS test_type, t.hand, t.started_at,"
        f" t.ended_at, t.status, t.fail_reason, t.markers_json, {result_cols},"
        " NULL AS details_json FROM tests t"
        " JOIN checks c ON c.id = t.check_id JOIN results r ON r.test_id = t.id"
        f" WHERE {' AND '.join(['t.status = ?', *clauses])}"
        " ORDER BY c.created_at, c.id, t.started_at, t.id"
    )
    out = []
    for r in conn.execute(sql, ["done", *args]):
        test = TestRow(
            id=r["test_id"],
            check_id=r["id"],
            type=cast(TestType, r["test_type"]),
            hand=cast(Hand, r["hand"]),
            started_at=_dt(r["started_at"]),
            ended_at=_opt_dt(r["ended_at"]),
            status=cast(TestStatus, r["status"]),
            fail_reason=cast(FailReason | None, r["fail_reason"]),
            markers=json.loads(r["markers_json"]) if r["markers_json"] else [],
        )
        out.append((_check_row(r), test, _result_row(r)))
    return out


def completed_check_times(
    conn: sqlite3.Connection, start: datetime | None, end: datetime | None
) -> list[datetime]:
    """created_at of checks with a done test, start <= created_at <= end, oldest first."""
    clauses, args = _range_clauses("c.created_at", start, end)
    done = "EXISTS (SELECT 1 FROM tests t WHERE t.check_id = c.id AND t.status = 'done')"
    rows = conn.execute(
        f"SELECT c.created_at FROM checks c WHERE {' AND '.join([done, *clauses])}"
        " ORDER BY c.created_at, c.id",
        args,
    )
    return [_dt(r["created_at"]) for r in rows]
