"""Writes generated SeedData to SQLite through db.queries, plus one replayable simulated check."""

import asyncio
import contextlib
import dataclasses
import sqlite3
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta

import numpy as np

from tremorlab.config import SimParams
from tremorlab.db import queries
from tremorlab.db.models import Hand, TestType
from tremorlab.seeding import SeedCheck, SeedData, SeedDose
from tremorlab.session import TestOutcome, TestSession
from tremorlab.sources.base import Batch, ImuBatch, TofBatch
from tremorlab.sources.simulated import SimulatedSource
from tremorlab.stream.broadcaster import Broadcaster

SEEDED_TEST_S: dict[TestType, float] = {"rest": 30.0, "posture": 30.0, "reach": 20.0, "tap": 10.0}
REPLAY_SIM = SimParams(tremor_hz=5.0, tremor_amp=0.5)
REPLAY_SEED = 42
REPLAY_AGE = timedelta(minutes=10)  # default replay check time: this long before now
REPLAY_HAND: Hand = "right"
LEAD_IN_S = 1.0
TREMOR_TEST_S = 30.0
BETWEEN_TESTS_S = 2.0
REACH_ATTEMPTS = 3
REACH_ATTEMPT_S = 5.0
TIME_DECIMALS = 6  # µs rounding keeps shifted sim timestamps bit-identical across runs


@contextlib.contextmanager
def _transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """One explicit transaction; the per-call commits in queries are no-ops in autocommit mode."""
    previous = conn.autocommit
    conn.autocommit = True
    conn.execute("BEGIN")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
    finally:
        conn.autocommit = previous


def write(
    conn: sqlite3.Connection,
    data: SeedData,
    *,
    replay_seed: int = REPLAY_SEED,
    replay_at: datetime | None = None,
) -> None:
    """Seeded rows, then the replay check at replay_at (default REPLAY_AGE ago), atomically."""
    at = datetime.now(UTC) - REPLAY_AGE if replay_at is None else replay_at
    last = max((c.created_at for c in data.checks), default=None)
    if last is not None and at <= last:
        raise ValueError(f"replay check at {at} must follow the last seeded check at {last}")
    with _transaction(conn):
        dose_ids = [queries.insert_dose(conn, d.taken_at, d.label) for d in data.doses]
        for check in data.checks:
            _write_check(conn, check, dose_ids)
        write_replay_check(conn, data, dose_ids, created_at=at, seed=replay_seed)


def _write_check(conn: sqlite3.Connection, c: SeedCheck, dose_ids: Sequence[int]) -> int:
    check_id = queries.insert_check(
        conn,
        created_at=c.created_at,
        minutes_since_dose=c.minutes_since_dose,
        notes=None,
        dose_id=None if c.dose_index is None else dose_ids[c.dose_index],
    )
    for t in c.tests:
        test_id = queries.insert_test(
            conn, check_id=check_id, type=t.type, hand=t.hand, started_at=t.started_at
        )
        queries.insert_result(conn, test_id, t.result)
        ended_at = t.started_at + timedelta(seconds=SEEDED_TEST_S[t.type])
        queries.finish_test(conn, test_id, ended_at=ended_at, status="done")
    return check_id


def _latest_dose(doses: Sequence[SeedDose], at: datetime) -> int | None:
    """Index of the latest dose taken at or before `at`."""
    before = [i for i, d in enumerate(doses) if d.taken_at <= at]
    return max(before, key=lambda i: doses[i].taken_at, default=None)


def write_replay_check(
    conn: sqlite3.Connection,
    data: SeedData,
    dose_ids: Sequence[int],
    *,
    created_at: datetime,
    seed: int,
) -> int:
    """The newest check: simulated rest, posture and reach recorded through TestSession."""
    dose_i = _latest_dose(data.doses, created_at)
    minutes = None
    if dose_i is not None:
        minutes = (created_at - data.doses[dose_i].taken_at) / timedelta(minutes=1)
    check_id = queries.insert_check(
        conn,
        created_at=created_at,
        minutes_since_dose=minutes,
        notes=None,
        dose_id=None if dose_i is None else dose_ids[dose_i],
    )
    asyncio.run(_record_replay_tests(conn, check_id, created_at.timestamp(), seed))
    return check_id


class _SimFeed:
    """Drives a fast SimulatedSource into a Broadcaster, shifting its timeline to start at t0."""

    def __init__(self, sim: SimulatedSource, broadcaster: Broadcaster, t0: float) -> None:
        self._batches = sim.batches()
        self._broadcaster = broadcaster
        self._t0 = t0
        self._sim_t0: float | None = None
        self._now = t0

    def now(self) -> float:
        """Epoch s of the newest dispatched sample; the session clock while recording."""
        return self._now

    async def advance(self, seconds: float) -> None:
        until = self._now + seconds
        while self._now < until:
            batch = self._shift(await anext(self._batches))
            if isinstance(batch, ImuBatch | TofBatch):
                self._now = max(self._now, float(batch.t[-1]))
            self._broadcaster.dispatch(batch)

    def _shift(self, b: Batch) -> Batch:
        if not isinstance(b, ImuBatch | TofBatch):
            return b
        if self._sim_t0 is None:
            self._sim_t0 = float(b.t[0])
        rel = np.round(b.t - self._sim_t0, TIME_DECIMALS)
        return dataclasses.replace(b, t=self._t0 + rel)


def _require_done(kind: TestType, outcome: TestOutcome) -> None:
    if outcome.status != "done":
        raise RuntimeError(f"simulated {kind} test failed: {outcome.fail_reason}")


async def _record_replay_tests(
    conn: sqlite3.Connection, check_id: int, t0: float, seed: int
) -> None:
    sim = SimulatedSource(REPLAY_SIM, fast=True, seed=seed)
    broadcaster = Broadcaster(sim)
    feed = _SimFeed(sim, broadcaster, t0)
    session = TestSession(conn, broadcaster, sim, clock=feed.now)
    tremor_kinds: tuple[TestType, ...] = ("rest", "posture")
    try:
        await feed.advance(LEAD_IN_S)
        for kind in tremor_kinds:
            test_id = session.start(check_id, kind, REPLAY_HAND)
            await feed.advance(TREMOR_TEST_S)
            _require_done(kind, session.stop(test_id))
            await feed.advance(BETWEEN_TESTS_S)
        test_id = session.start(check_id, "reach", REPLAY_HAND)
        for _ in range(REACH_ATTEMPTS):
            session.mark(test_id)
            sim.trigger_descent()
            await feed.advance(REACH_ATTEMPT_S)
        _require_done("reach", session.stop(test_id))
    finally:
        await sim.stop()
