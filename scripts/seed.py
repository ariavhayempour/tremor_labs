"""Seed a SQLite DB with deterministic demo data plus one replayable simulated check."""

import argparse
import sys
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

from tremorlab import seeding
from tremorlab.db.connection import connect
from tremorlab.db.seed_writer import write

SIDECAR_SUFFIXES = ("", "-wal", "-shm")  # SQLite WAL mode keeps two companion files


def reset(db: Path) -> None:
    for suffix in SIDECAR_SUFFIXES:
        db.with_name(db.name + suffix).unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="SQLite file to write")
    parser.add_argument("--reset", action="store_true", help="delete the DB file first")
    parser.add_argument("--seed", type=int, default=42, help="random seed (default 42)")
    parser.add_argument("--days", type=int, default=14, help="days of history (default 14)")
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=None,
        help="last seeded local day, YYYY-MM-DD (default yesterday)",
    )
    args = parser.parse_args(argv)
    if args.reset:
        reset(args.db)
    end = args.end or date.today() - timedelta(days=1)
    data = seeding.generate(seed=args.seed, days=args.days, end=end)
    conn = connect(args.db)
    try:
        write(conn, data, replay_seed=args.seed)
    finally:
        conn.close()
    print(
        f"seeded {len(data.doses)} doses, {len(data.checks)} checks + 1 replay check into {args.db}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
