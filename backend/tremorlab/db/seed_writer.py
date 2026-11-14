"""Writes generated SeedData to SQLite through db.queries."""

import sqlite3

from tremorlab.seeding import SeedData


def write(conn: sqlite3.Connection, data: SeedData) -> None:
    raise NotImplementedError
