"""Lifestyle factors were removed: effects too small and confounded to report reliably."""

import dataclasses
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tremorlab.analysis import insights
from tremorlab.api import schemas
from tremorlab.db.models import CheckRow
from tremorlab.seeding import SeedCheck

FACTORS = ("caffeine", "sleep_quality", "stress", "alcohol")
SCHEMA = Path(__file__).resolve().parents[1] / "tremorlab" / "db" / "schema.sql"


@pytest.mark.parametrize("field", FACTORS)
def test_check_in_rejects_factor_fields(client: TestClient, field: str) -> None:
    r = client.post("/api/checks", json={"medication": "not_yet", field: 1})
    assert r.status_code == 422 and r.json()["error"] == "validation_error"


def test_check_out_has_no_factor_fields(client: TestClient) -> None:
    assert client.post("/api/checks", json={"medication": "not_yet"}).status_code == 201
    [check] = client.get("/api/checks").json()
    assert not set(FACTORS) & set(check)


def test_factors_endpoint_is_gone(client: TestClient) -> None:
    assert client.get("/api/insights/factors").status_code == 404


def test_no_factor_columns_in_schema() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA.read_text())
    cols = {r[1] for r in conn.execute("PRAGMA table_info(checks)")}
    assert not set(FACTORS) & cols


def test_no_factor_fields_in_models() -> None:
    for cls in (CheckRow, SeedCheck, insights.Obs):
        assert not set(FACTORS) & {f.name for f in dataclasses.fields(cls)}, cls.__name__
    for model in (schemas.CheckInRequest, schemas.CheckOut, schemas.ReportOut):
        assert not (set(FACTORS) | {"factors"}) & set(model.model_fields), model.__name__
    assert not hasattr(schemas, "FactorEffect") and not hasattr(insights, "factor_effects")
