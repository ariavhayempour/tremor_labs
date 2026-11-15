"""Runtime configuration, read once from environment variables."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SensorSourceName = Literal["sim", "board", "replay"]
SENSOR_SOURCES: tuple[SensorSourceName, ...] = ("sim", "board", "replay")
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tremorlab.db"


@dataclass(frozen=True)
class SimParams:
    """Simulator parameters. Amplitudes and noise in m/s², distances in mm, frequency in Hz."""

    tremor_hz: float = 5.0
    tremor_amp: float = 0.3
    noise: float = 0.02
    hand_mm: float = 200.0
    reach_wobble: float = 0.0


@dataclass(frozen=True)
class Config:
    sensor_source: SensorSourceName
    sim: SimParams
    board_host: str = "127.0.0.1"
    board_port: int = 7700
    db_path: Path = field(default=DEFAULT_DB_PATH)
    cors_origin: str = "http://localhost:5173"
    replay_test_id: int | None = None


def _float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as e:
        raise ValueError(f"{name} must be a number, got {raw!r}") from e


def _int(env: Mapping[str, str], name: str, default: int | None) -> int | None:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from e


def load_config(env: Mapping[str, str] = os.environ) -> Config:
    """Build a Config from env vars; raises ValueError on invalid values."""
    source = env.get("SENSOR_SOURCE", "sim") or "sim"
    if source not in SENSOR_SOURCES:
        raise ValueError(f"SENSOR_SOURCE must be one of {SENSOR_SOURCES}, got {source!r}")
    defaults = SimParams()
    sim = SimParams(
        tremor_hz=_float(env, "SIM_TREMOR_HZ", defaults.tremor_hz),
        tremor_amp=_float(env, "SIM_TREMOR_AMP", defaults.tremor_amp),
        noise=_float(env, "SIM_NOISE", defaults.noise),
        hand_mm=_float(env, "SIM_HAND_MM", defaults.hand_mm),
        reach_wobble=_float(env, "SIM_REACH_WOBBLE", defaults.reach_wobble),
    )
    port = _int(env, "BOARD_PORT", 7700)
    assert port is not None
    db_path = env.get("DB_PATH")
    return Config(
        sensor_source=source,
        sim=sim,
        board_host=env.get("BOARD_HOST") or "127.0.0.1",
        board_port=port,
        db_path=Path(db_path) if db_path else DEFAULT_DB_PATH,
        cors_origin=env.get("CORS_ORIGIN") or "http://localhost:5173",
        replay_test_id=_int(env, "REPLAY_TEST_ID", None),
    )
