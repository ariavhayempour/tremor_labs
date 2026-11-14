import dataclasses
import importlib
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tremorlab.config import load_config
from tremorlab.main import create_app

REPO = Path(__file__).resolve().parents[2]
CONTRACTS = REPO / "docs" / "contracts.md"
SCHEMA = REPO / "backend" / "tremorlab" / "db" / "schema.sql"
ENDPOINT_HEADING = re.compile(r"^#{3,4} `(GET|POST|PUT|DELETE|WS) (/[^`\s?]*)", re.MULTILINE)


def contract_endpoints() -> list[tuple[str, str]]:
    return ENDPOINT_HEADING.findall(CONTRACTS.read_text())


def app_endpoints(app: FastAPI) -> set[tuple[str, str]]:
    """HTTP endpoints from the OpenAPI schema (WebSocket routes are not listed there)."""
    paths: dict[str, dict[str, object]] = app.openapi()["paths"]
    return {(method.upper(), path) for path, ops in paths.items() for method in ops}


def test_schema_applies_to_memory_db() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA.read_text())
    conn.executescript(SCHEMA.read_text())  # idempotent: IF NOT EXISTS throughout
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"checks", "tests", "results", "raw_samples", "doses", "settings"}


def test_schema_has_extension_columns() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA.read_text())

    def cols(table: str) -> set[str]:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}

    assert "dose_id" in cols("checks")
    assert {"markers_json", "fail_reason"} <= cols("tests")
    assert "details_json" in cols("results")


def test_schema_rejects_bad_test_status(mem_conn: sqlite3.Connection) -> None:
    mem_conn.execute("INSERT INTO checks(created_at) VALUES ('2026-11-14T10:00:00+00:00')")
    with pytest.raises(sqlite3.IntegrityError):
        mem_conn.execute(
            "INSERT INTO tests(check_id, type, hand, started_at, status) "
            "VALUES (1, 'rest', 'right', '2026-11-14T10:00:00+00:00', 'paused')"
        )


def test_contracts_doc_lists_endpoints() -> None:
    assert len(contract_endpoints()) >= 20


def test_every_router_registered(client: TestClient) -> None:
    http = {e for e in contract_endpoints() if e[0] != "WS"}
    missing = http - app_endpoints(client.app)  # type: ignore[arg-type]
    assert not missing, f"endpoints in docs/contracts.md but not in the app: {sorted(missing)}"


def test_every_websocket_registered(client: TestClient) -> None:
    ws_paths = [path for method, path in contract_endpoints() if method == "WS"]
    assert ws_paths == ["/ws"]
    with client.websocket_connect("/ws"):
        pass  # a missing route would raise during the handshake


def test_sim_routes_only_mounted_for_sim(tmp_path: Path) -> None:
    config = load_config({"SENSOR_SOURCE": "board", "DB_PATH": str(tmp_path / "t.db")})
    paths = {path for _, path in app_endpoints(create_app(config))}
    assert "/api/sim" not in paths and "/api/health" in paths


@pytest.mark.parametrize(
    ("module", "names"),
    [
        ("tremorlab.analysis.errors", ["AnalysisError"]),
        (
            "tremorlab.analysis.sampling",
            ["effective_fs", "trim_edges", "needs_resample", "resample_uniform", "max_gap"],
        ),
        (
            "tremorlab.analysis.tremor",
            ["TremorResult", "strength_to_score", "tremor_spectrum", "analyze_tremor"],
        ),
        ("tremorlab.analysis.posture", ["band_from_start", "in_band_mask", "analyze_posture"]),
        (
            "tremorlab.analysis.reach",
            ["ReachAttempt", "ReachResult", "detect_descent", "analyze_reach"],
        ),
        ("tremorlab.analysis.tap", ["TapFrame", "TapResult", "tap_signal", "analyze_taps"]),
        ("tremorlab.analysis.baseline", ["compare"]),
        (
            "tremorlab.analysis.insights",
            [
                "Obs",
                "Bin",
                "FactorEffect",
                "ProfileRow",
                "DayPoint",
                "dose_response",
                "returns_after_h",
                "factor_effects",
                "profile",
                "daily_timeline",
                "streak_days",
            ],
        ),
        ("tremorlab.seeding", ["generate", "SeedData"]),
        ("tremorlab.db.seed_writer", ["write"]),
        ("tremorlab.db.models", ["CheckRow", "TestRow", "ResultRow", "DoseRow"]),
        ("tremorlab.sources.simulated", ["SimulatedSource"]),
        (
            "tremorlab.sources.board",
            ["BoardSource", "parse_line", "MicrosUnwrapper", "decode_imu", "decode_tof"],
        ),
        ("tremorlab.sources.replay", ["ReplaySource", "make_replay_source"]),
    ],
)
def test_analysis_stubs_import(module: str, names: list[str]) -> None:
    mod = importlib.import_module(module)
    for name in names:
        assert hasattr(mod, name), f"{module}.{name} missing"


def test_analyzers_bundle_fields() -> None:
    from tremorlab.analysis import Analyzers

    assert [f.name for f in dataclasses.fields(Analyzers)] == ["tremor", "posture", "reach", "tap"]


def test_analysis_error_carries_code() -> None:
    from tremorlab.analysis.errors import AnalysisError

    err = AnalysisError("no_taps_detected")
    assert err.code == "no_taps_detected"


def test_queries_signatures_exist() -> None:
    from tremorlab.db import queries

    for name in [
        "insert_check",
        "get_check",
        "list_checks",
        "insert_test",
        "finish_test",
        "tests_for_check",
        "fail_stale_recordings",
        "insert_result",
        "get_result",
        "insert_raw",
        "raw_for_test",
        "insert_dose",
        "dose_near",
        "latest_dose_at_or_before",
        "list_doses",
        "get_settings",
        "put_settings",
        "results_history",
    ]:
        assert callable(getattr(queries, name)), name
