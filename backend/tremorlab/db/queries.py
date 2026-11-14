"""All SQL lives here. Every function takes the connection first; datetimes are UTC-aware."""

import sqlite3
from datetime import datetime
from typing import Any

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


def insert_check(
    conn: sqlite3.Connection,
    *,
    created_at: datetime,
    minutes_since_dose: float | None,
    caffeine: bool | None,
    sleep_quality: int | None,
    stress: int | None,
    alcohol: bool | None,
    notes: str | None,
    dose_id: int | None,
) -> int:
    raise NotImplementedError


def get_check(conn: sqlite3.Connection, check_id: int) -> CheckRow | None:
    raise NotImplementedError


def list_checks(
    conn: sqlite3.Connection, start: datetime | None, end: datetime | None
) -> list[CheckRow]:
    raise NotImplementedError


def insert_test(
    conn: sqlite3.Connection, *, check_id: int, type: TestType, hand: Hand, started_at: datetime
) -> int:
    raise NotImplementedError


def finish_test(
    conn: sqlite3.Connection,
    test_id: int,
    *,
    ended_at: datetime,
    status: TestStatus,
    fail_reason: FailReason | None = None,
    markers: list[float] | None = None,
) -> None:
    raise NotImplementedError


def tests_for_check(conn: sqlite3.Connection, check_id: int) -> list[TestRow]:
    raise NotImplementedError


def fail_stale_recordings(conn: sqlite3.Connection, *, older_than: datetime | None = None) -> int:
    """Recording tests started before older_than (all if None) → failed/interrupted; count."""
    raise NotImplementedError


def insert_result(conn: sqlite3.Connection, test_id: int, r: ResultRow) -> None:
    raise NotImplementedError


def get_result(conn: sqlite3.Connection, test_id: int) -> ResultRow | None:
    raise NotImplementedError


def insert_raw(
    conn: sqlite3.Connection, test_id: int, sensor: Sensor, payload: dict[str, Any]
) -> None:
    raise NotImplementedError


def raw_for_test(conn: sqlite3.Connection, test_id: int) -> list[tuple[Sensor, dict[str, Any]]]:
    raise NotImplementedError


def insert_dose(conn: sqlite3.Connection, taken_at: datetime, label: str | None = None) -> int:
    raise NotImplementedError


def dose_near(
    conn: sqlite3.Connection, t: datetime, minutes: float = DOSE_MATCH_MINUTES
) -> DoseRow | None:
    raise NotImplementedError


def latest_dose_at_or_before(conn: sqlite3.Connection, t: datetime) -> DoseRow | None:
    raise NotImplementedError


def list_doses(
    conn: sqlite3.Connection, start: datetime | None, end: datetime | None
) -> list[DoseRow]:
    raise NotImplementedError


def get_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    raise NotImplementedError


def put_settings(conn: sqlite3.Connection, values: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError


def results_history(
    conn: sqlite3.Connection, test_type: TestType, before: datetime, limit: int | None = None
) -> list[tuple[CheckRow, ResultRow]]:
    """Done tests of test_type from checks before `before`, newest first."""
    raise NotImplementedError
