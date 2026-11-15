"""Builds CheckOut and the Results-screen cards from stored checks, tests and results."""

import dataclasses
import sqlite3

from tremorlab.analysis import baseline
from tremorlab.api.schemas import CardOut, CheckOut, CheckSummaryOut, TestOut
from tremorlab.db import queries
from tremorlab.db.models import CheckRow, ResultRow, TestRow, TestType
from tremorlab.session import result_out

CARD_ORDER: tuple[TestType, ...] = ("rest", "posture", "reach", "tap")
CARD_METRICS: dict[TestType, tuple[str, str]] = {
    "rest": ("strength_score", "score"),
    "posture": ("strength_score", "score"),
    "reach": ("smoothness", "mm"),
    "tap": ("taps_per_sec", "taps/s"),
}


def to_test_out(conn: sqlite3.Connection, t: TestRow, *, details: bool = True) -> TestOut:
    result = queries.get_result(conn, t.id)
    if result is not None and not details:
        result = dataclasses.replace(result, details={})  # metrics only; curves are bulky
    return TestOut(
        id=t.id,
        type=t.type,
        hand=t.hand,
        status=t.status,
        fail_reason=t.fail_reason,
        result=None if result is None else result_out(result),
    )


def to_check_out(
    conn: sqlite3.Connection, c: CheckRow, tests: list[TestRow], *, details: bool = True
) -> CheckOut:
    return CheckOut(
        id=c.id,
        created_at=c.created_at,
        minutes_since_dose=c.minutes_since_dose,
        notes=c.notes,
        dose_id=c.dose_id,
        tests=[to_test_out(conn, t, details=details) for t in tests],
    )


def metric(test_type: TestType, r: ResultRow) -> float | None:
    value: float | None = getattr(r, CARD_METRICS[test_type][0])
    return value


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def check_value(
    conn: sqlite3.Connection, test_type: TestType, tests: list[TestRow]
) -> float | None:
    """Latest done test's metric; for tap, the mean over hands of each hand's latest done test."""
    latest: dict[str, ResultRow] = {}
    for t in tests:
        if t.type == test_type and t.status == "done":
            r = queries.get_result(conn, t.id)
            if r is not None and metric(test_type, r) is not None:
                latest[t.hand if test_type == "tap" else "any"] = r
    values = [v for r in latest.values() if (v := metric(test_type, r)) is not None]
    return _mean(values)


def history_values(conn: sqlite3.Connection, test_type: TestType, c: CheckRow) -> list[float]:
    """One value per earlier check, newest first; tap averages that check's done hands."""
    per_check: dict[int, list[float]] = {}
    for hist_check, r in queries.results_history(conn, test_type, before=c.created_at):
        value = metric(test_type, r)
        if value is None:
            continue
        if test_type == "tap":
            per_check.setdefault(hist_check.id, []).append(value)
        else:
            per_check.setdefault(hist_check.id, [value])  # newest test of that check wins
    return [v for vals in per_check.values() if (v := _mean(vals)) is not None]


def card(
    conn: sqlite3.Connection, test_type: TestType, c: CheckRow, tests: list[TestRow]
) -> CardOut:
    name, unit = CARD_METRICS[test_type]
    value = check_value(conn, test_type, tests)
    history = history_values(conn, test_type, c)
    tried = any(t.type == test_type for t in tests)
    status = "done" if value is not None else "failed" if tried else "missing"
    # Below the minimum the contract requires null, so compare only runs with enough history.
    enough = len(history) >= baseline.BASELINE_MIN_N
    pct = baseline.compare(value, history) if value is not None and enough else None
    return CardOut(
        test=test_type,
        metric=name,
        value=value,
        unit=unit,
        baseline_pct=pct,
        baseline_n=len(history),
        status=status,
    )


def check_summary(conn: sqlite3.Connection, c: CheckRow) -> CheckSummaryOut:
    tests = queries.tests_for_check(conn, c.id)
    return CheckSummaryOut(
        check=to_check_out(conn, c, tests),
        cards=[card(conn, test_type, c, tests) for test_type in CARD_ORDER],
    )
