"""Check-in dose logging: which dose a check is measured from, and the minutes since it."""

import sqlite3
from datetime import datetime, timedelta
from typing import Literal

from tremorlab.db import queries

Medication = Literal["now", "hours_ago", "not_yet"]


def resolve_dose(
    conn: sqlite3.Connection, now: datetime, medication: Medication, hours_ago: float | None
) -> tuple[int | None, float | None]:
    """(dose_id, minutes since that dose); logs a dose for "now"/"hours_ago" unless one is near."""
    if medication == "not_yet":
        latest = queries.latest_dose_at_or_before(conn, now)
        return (None, None) if latest is None else (latest.id, _minutes(now, latest.taken_at))
    offset_h = 0.0
    if medication == "hours_ago":
        if hours_ago is None:
            raise ValueError("hours_ago is required when medication is hours_ago")
        offset_h = hours_ago
    taken_at = now - timedelta(hours=offset_h)
    near = queries.dose_near(conn, taken_at)
    if near is not None:
        return near.id, _minutes(now, near.taken_at)
    return queries.insert_dose(conn, taken_at), _minutes(now, taken_at)


def _minutes(now: datetime, taken_at: datetime) -> float:
    # A reused dose can sit slightly after now; time since a dose is never negative.
    return max(0.0, (now - taken_at).total_seconds() / 60.0)
