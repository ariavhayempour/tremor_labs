"""User settings: defaults merged with the stored values."""

import sqlite3
from typing import Any

from fastapi import APIRouter, Request

from tremorlab.api.schemas import SettingsModel, SettingsUpdate
from tremorlab.db import queries

router = APIRouter(prefix="/api", tags=["settings"])
CLEARABLE = {"posture_band"}


def _conn(request: Request) -> sqlite3.Connection:
    conn: sqlite3.Connection = request.app.state.conn
    return conn


def current(conn: sqlite3.Connection) -> SettingsModel:
    """Unknown stored keys are ignored so a renamed setting can't break the endpoint."""
    stored = queries.get_settings(conn)
    known = {k: v for k, v in stored.items() if k in SettingsModel.model_fields}
    return SettingsModel(**(SettingsModel().model_dump() | known))


@router.get("/settings")
def get_settings(request: Request) -> SettingsModel:
    return current(_conn(request))


@router.put("/settings")
def put_settings(request: Request, body: SettingsUpdate) -> SettingsModel:
    conn = _conn(request)
    sent = body.model_dump(exclude_unset=True)
    changes: dict[str, Any] = {k: v for k, v in sent.items() if v is not None or k in CLEARABLE}
    merged = SettingsModel(**(current(conn).model_dump() | changes))
    queries.put_settings(conn, {k: getattr(merged, k) for k in changes})
    return merged
