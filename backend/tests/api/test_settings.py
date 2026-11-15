from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.fakes import FakeClock, QuietSource
from tremorlab.config import Config
from tremorlab.db import queries as q
from tremorlab.main import create_app
from tremorlab.session import TestSession

DEFAULTS = {
    "dose_times": ["08:00", "13:00", "18:00"],
    "reminder_times": [],
    "tested_hand": "right",
    "posture_band": None,
}


@pytest.fixture
def client(config: Config) -> Iterator[TestClient]:
    with TestClient(create_app(config, source=QuietSource(), clock=FakeClock())) as c:
        yield c


def put(client: TestClient, body: dict[str, Any]) -> Any:
    r = client.put("/api/settings", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_defaults(client: TestClient) -> None:
    r = client.get("/api/settings")
    assert r.status_code == 200 and r.json() == DEFAULTS


def test_put_roundtrip(client: TestClient) -> None:
    out = put(client, {"dose_times": ["07:30"], "posture_band": [150, 260]})
    expected = DEFAULTS | {"dose_times": ["07:30"], "posture_band": [150.0, 260.0]}
    assert out == expected
    assert put(client, {"tested_hand": "left"}) == expected | {"tested_hand": "left"}
    assert client.get("/api/settings").json() == expected | {"tested_hand": "left"}


def test_explicit_null_clears_band_but_omitted_keeps_it(client: TestClient) -> None:
    put(client, {"posture_band": [150, 260]})
    assert put(client, {"reminder_times": ["20:00"]})["posture_band"] == [150.0, 260.0]
    assert put(client, {"posture_band": None})["posture_band"] is None


def test_null_list_or_hand_keeps_stored_value(client: TestClient) -> None:
    put(client, {"dose_times": ["09:00"], "tested_hand": "left"})
    out = put(client, {"dose_times": None, "tested_hand": None})
    assert out["dose_times"] == ["09:00"] and out["tested_hand"] == "left"


@pytest.mark.parametrize(
    "body",
    [
        {"dose_times": ["8:00"]},
        {"dose_times": ["24:00"]},
        {"reminder_times": ["noon"]},
        {"posture_band": [260, 150]},
        {"posture_band": [0, 2500]},
        {"tested_hand": "both"},
        {"caffeine_cups": 2},
    ],
)
def test_rejects_bad_values(client: TestClient, body: dict[str, Any]) -> None:
    r = client.put("/api/settings", json=body)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
    assert client.get("/api/settings").json() == DEFAULTS


def test_stored_unknown_keys_are_ignored(client: TestClient) -> None:
    q.put_settings(client.app.state.conn, {"old_key": 1})  # type: ignore[attr-defined]
    assert client.get("/api/settings").json() == DEFAULTS


def test_posture_band_used_by_session(client: TestClient) -> None:
    put(client, {"posture_band": [120, 200]})
    check_id = client.post("/api/checks", json={"medication": "not_yet"}).json()["check_id"]
    r = client.post(f"/api/checks/{check_id}/tests", json={"type": "posture", "hand": "right"})
    assert r.status_code == 201, r.text
    session: TestSession = client.app.state.session  # type: ignore[attr-defined]
    assert session.active is not None and session.active.band == (120.0, 200.0)
