"""Opens the SQLite database with the pragmas the app relies on and applies schema.sql."""

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
MEMORY = ":memory:"


def connect(path: Path | str) -> sqlite3.Connection:
    """Open (creating parent dirs) with Row rows, foreign keys, WAL and the schema applied."""
    if str(path) != MEMORY:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")  # WAL-safe; avoids an fsync per raw-sample insert
    conn.executescript(SCHEMA_PATH.read_text())
    return conn
