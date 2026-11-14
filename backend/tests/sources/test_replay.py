import asyncio
import sqlite3
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from tests.api.fakes import DATA_T0, sim_batches
from tremorlab.analysis.tremor import analyze_tremor
from tremorlab.config import Config, SimParams, load_config
from tremorlab.db import queries as q
from tremorlab.db.connection import connect
from tremorlab.db.models import TestStatus, TestType
from tremorlab.sources import make_source
from tremorlab.sources.base import Batch, ImuBatch, SourceStatus, TofBatch
from tremorlab.sources.replay import LOOP_GAP_S, ReplaySource, make_replay_source
from tremorlab.stream.recorder import Recorder

REPLAY_NOW = 1_900_000_000.0
T = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    c = connect(":memory:")
    yield c
    c.close()


def new_check(conn: sqlite3.Connection, at: datetime = T) -> int:
    return q.insert_check(
        conn,
        created_at=at,
        minutes_since_dose=None,
        caffeine=None,
        sleep_quality=None,
        stress=None,
        alcohol=None,
        notes=None,
        dose_id=None,
    )


def record(
    conn: sqlite3.Connection,
    check_id: int,
    kind: TestType,
    batches: list[ImuBatch | TofBatch],
    status: TestStatus = "done",
) -> int:
    """Store batches as the session would (raw payloads), then finish the test."""
    tid = q.insert_test(conn, check_id=check_id, type=kind, hand="right", started_at=T)
    rec = Recorder(tid, kind, 0.0, None)
    for b in batches:
        rec.add(b)
    for sensor, payload in rec.raw_payloads():
        q.insert_raw(conn, tid, sensor, payload)
    q.finish_test(conn, tid, ended_at=T, status=status)
    return tid


def collect(source: ReplaySource, n: int) -> list[Batch]:
    """The first n batches (SourceStatus included)."""

    async def go() -> list[Batch]:
        await source.start()
        out: list[Batch] = []
        async for b in source.batches():
            out.append(b)
            if len(out) >= n:
                break
        await source.stop()
        return out

    return asyncio.run(go())


def data(batches: list[Batch]) -> tuple[list[ImuBatch], list[TofBatch]]:
    return (
        [b for b in batches if isinstance(b, ImuBatch)],
        [b for b in batches if isinstance(b, TofBatch)],
    )


def replay(conn: sqlite3.Connection, ids: list[int]) -> ReplaySource:
    return ReplaySource(conn, ids, fast=True, clock=lambda: REPLAY_NOW)


def test_replay_roundtrip_peak_matches_original(conn: sqlite3.Connection) -> None:
    tid = record(conn, new_check(conn), "rest", sim_batches(32, SimParams(tremor_hz=6.0)))
    imu, _ = data(collect(replay(conn, [tid]), 1 + 640))
    assert len(imu) == 320
    t = np.concatenate([b.t for b in imu])
    acc = np.vstack([b.acc for b in imu])
    r = analyze_tremor(t, acc)
    assert r.peak_hz is not None and abs(r.peak_hz - 6.0) <= 0.25


def test_replay_first_batch_is_source_status(conn: sqlite3.Connection) -> None:
    tid = record(conn, new_check(conn), "rest", sim_batches(1))
    [first, second] = collect(replay(conn, [tid]), 2)
    assert isinstance(first, SourceStatus) and first.connected is True
    assert first.sensors == {"movement": True, "distance": True}
    assert isinstance(second, ImuBatch | TofBatch)


def test_replay_loops(conn: sqlite3.Connection) -> None:
    original = sim_batches(2)
    tid = record(conn, new_check(conn), "rest", original)
    imu, tof = data(collect(replay(conn, [tid]), 1 + 100))
    assert len(imu) == len(tof) == 50
    for i in range(30):
        np.testing.assert_array_equal(imu[i].acc, imu[i + 20].acc)
        np.testing.assert_array_equal(imu[i].gyro, imu[i + 20].gyro)
        np.testing.assert_array_equal(tof[i].mm, tof[i + 20].mm)
    np.testing.assert_allclose(imu[0].acc, original[0].acc)


def test_replay_timestamps_monotonic_across_loop(conn: sqlite3.Connection) -> None:
    tid = record(conn, new_check(conn), "rest", sim_batches(2))
    imu, tof = data(collect(replay(conn, [tid]), 1 + 100))
    for batches in (imu, tof):
        t = np.concatenate([b.t for b in batches])
        assert np.all(np.diff(t) > 0)
        assert np.max(np.diff(t)) < LOOP_GAP_S + 0.03
    t_imu = np.concatenate([b.t for b in imu])
    assert t_imu[0] == pytest.approx(REPLAY_NOW)  # shifted to now
    np.testing.assert_allclose(np.diff(imu[0].t), 0.01, atol=1e-6)  # float64 epoch resolution


def test_replay_tof_uses_per_sample_offsets(conn: sqlite3.Connection) -> None:
    tid = q.insert_test(conn, check_id=new_check(conn), type="reach", hand="right", started_at=T)
    imu = {"type": "imu", "t0": 100.0, "fs": 100.0, "samples": [[0, 0, 9.8, 0, 0, 0]] * 10}
    tof = {"type": "tof", "t0": 100.0, "fs": 40.0, "t": [0.0, 0.02, 0.07], "samples_mm": [1, 2, 3]}
    q.insert_raw(conn, tid, "imu", imu)
    q.insert_raw(conn, tid, "tof", tof)
    imu_b, tof_b = data(collect(replay(conn, [tid]), 3))
    [b] = tof_b
    np.testing.assert_allclose(np.diff(b.t), [0.02, 0.05], atol=1e-6)  # float64 epoch resolution
    assert b.t[0] == pytest.approx(REPLAY_NOW) and b.mm.tolist() == [1.0, 2.0, 3.0]
    assert imu_b[0].acc.shape == (10, 3) and imu_b[0].gyro.shape == (10, 3)


def test_replay_tof_without_offsets_falls_back_to_fs(conn: sqlite3.Connection) -> None:
    tid = q.insert_test(conn, check_id=new_check(conn), type="reach", hand="right", started_at=T)
    q.insert_raw(conn, tid, "tof", {"type": "tof", "t0": 5.0, "fs": 40.0, "samples_mm": [1, 2, 3]})
    [_, b] = collect(replay(conn, [tid]), 2)
    assert isinstance(b, TofBatch)
    np.testing.assert_allclose(np.diff(b.t), [0.025, 0.025], atol=1e-6)  # float64 epoch resolution


def test_replay_concatenates_tests_in_order(conn: sqlite3.Connection) -> None:
    check_id = new_check(conn)
    rest = record(conn, check_id, "rest", sim_batches(1, SimParams(hand_mm=100.0)))
    late = sim_batches(1, SimParams(hand_mm=500.0), t0=DATA_T0 + 600.0)
    posture = record(conn, check_id, "posture", late)
    imu, tof = data(collect(replay(conn, [rest, posture]), 1 + 40))
    assert [round(float(np.mean(b.mm)), -2) for b in tof] == [100.0] * 10 + [500.0] * 10
    t = np.concatenate([b.t for b in imu])
    assert np.all(np.diff(t) > 0) and np.max(np.diff(t)) < LOOP_GAP_S + 0.03


def test_replay_health_always_connected(conn: sqlite3.Connection) -> None:
    tid = record(conn, new_check(conn), "rest", sim_batches(3))
    source = replay(conn, [tid])
    h = source.health()
    assert h.connected is True and h.sensors_detected == {"movement": True, "distance": True}
    collect(source, 1 + 40)
    h = source.health()
    assert h.imu_hz == pytest.approx(100.0, rel=0.01)
    assert h.tof_hz == pytest.approx(40.0, rel=0.01)
    assert source.name == "replay"


def test_replay_is_paced_in_real_time(conn: sqlite3.Connection) -> None:
    tid = record(conn, new_check(conn), "rest", sim_batches(0.5))
    source = ReplaySource(conn, [tid])
    began = time.time()
    imu, _ = data(collect(source, 1 + 10))
    elapsed = time.time() - began
    assert 0.35 <= elapsed < 1.5
    assert imu[-1].t[-1] == pytest.approx(time.time(), abs=0.15)


def test_replay_led_is_noop(conn: sqlite3.Connection) -> None:
    tid = record(conn, new_check(conn), "rest", sim_batches(1))
    asyncio.run(replay(conn, [tid]).led("countdown", 3))


def test_replay_without_data_raises(conn: sqlite3.Connection) -> None:
    tid = q.insert_test(conn, check_id=new_check(conn), type="rest", hand="right", started_at=T)
    with pytest.raises(ValueError, match="no raw samples"):
        replay(conn, [tid])


def replay_config(tmp_path: Path, **env: str) -> Config:
    return load_config({"DB_PATH": str(tmp_path / "replay.db"), "SENSOR_SOURCE": "replay", **env})


def seed_checks(config: Config) -> dict[str, int]:
    conn = connect(config.db_path)
    ids: dict[str, int] = {}
    full = new_check(conn, T)
    for kind in ("rest", "posture", "reach"):
        ids[kind] = record(conn, full, kind, sim_batches(1))  # type: ignore[arg-type]
    ids["retry_rest"] = record(conn, full, "rest", sim_batches(1))
    partial = new_check(conn, T + timedelta(hours=1))
    record(conn, partial, "rest", sim_batches(1))
    record(conn, partial, "posture", sim_batches(1))
    record(conn, partial, "reach", sim_batches(1), status="failed")
    conn.close()
    return ids


def test_make_replay_source_uses_latest_full_check(tmp_path: Path) -> None:
    config = replay_config(tmp_path)
    ids = seed_checks(config)
    source = make_replay_source(config)
    assert source.test_ids == [ids["retry_rest"], ids["posture"], ids["reach"]]
    assert isinstance(collect(source, 2)[1], ImuBatch | TofBatch)


def test_make_replay_source_uses_replay_test_id(tmp_path: Path) -> None:
    ids = seed_checks(replay_config(tmp_path))
    source = make_source(replay_config(tmp_path, REPLAY_TEST_ID=str(ids["posture"])))
    assert isinstance(source, ReplaySource) and source.test_ids == [ids["posture"]]


def test_make_replay_source_without_full_check_raises(tmp_path: Path) -> None:
    config = replay_config(tmp_path)
    conn = connect(config.db_path)
    record(conn, new_check(conn), "rest", sim_batches(1))
    conn.close()
    with pytest.raises(ValueError, match="REPLAY_TEST_ID"):
        make_replay_source(config)


def test_app_runs_on_replay_source(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from tremorlab.main import create_app

    config = replay_config(tmp_path)
    seed_checks(config)
    with TestClient(create_app(config)) as client:
        body = client.get("/api/health").json()
        assert body["sensor_source"] == "replay" and body["connected"] is True
        with client.websocket_connect("/ws") as ws:
            kinds = {ws.receive_json()["type"] for _ in range(6)}
        assert {"imu", "tof"} <= kinds
