import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tremorlab.config import Config, load_config
from tremorlab.main import create_app

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "tremorlab" / "db" / "schema.sql"


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """Simulator config whose DB lives in the test's temp dir, never in backend/data."""
    return load_config({"DB_PATH": str(tmp_path / "test.db")})


@pytest.fixture
def client(config: Config) -> Iterator[TestClient]:
    """TestClient used as a context manager so the app lifespan runs."""
    with TestClient(create_app(config)) as c:
        yield c


@pytest.fixture
def mem_conn() -> Iterator[sqlite3.Connection]:
    """In-memory SQLite with the schema applied and foreign keys on."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_PATH.read_text())
    yield conn
    conn.close()
