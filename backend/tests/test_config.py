from pathlib import Path

import pytest

from tremorlab.config import DEFAULT_DB_PATH, load_config


def test_load_config_defaults() -> None:
    c = load_config({})
    assert c.sensor_source == "sim" and c.sim.tremor_hz == 5.0 and c.board_port == 7700
    assert c.sim.tremor_amp == 0.3 and c.sim.noise == 0.02 and c.sim.hand_mm == 200.0
    assert c.sim.reach_wobble == 0.0
    assert c.board_host == "127.0.0.1" and c.cors_origin == "http://localhost:5173"
    assert c.replay_test_id is None


def test_default_db_path_is_backend_data() -> None:
    c = load_config({})
    assert c.db_path == DEFAULT_DB_PATH
    assert c.db_path.parts[-3:] == ("backend", "data", "tremorlab.db")


def test_load_config_env_overrides() -> None:
    c = load_config({"SIM_TREMOR_HZ": "6.5", "SENSOR_SOURCE": "board"})
    assert c.sim.tremor_hz == 6.5 and c.sensor_source == "board"


def test_load_config_reads_every_env_name() -> None:
    c = load_config(
        {
            "SENSOR_SOURCE": "replay",
            "SIM_TREMOR_AMP": "0.5",
            "SIM_NOISE": "0.1",
            "SIM_HAND_MM": "250",
            "SIM_REACH_WOBBLE": "6",
            "BOARD_HOST": "10.0.0.2",
            "BOARD_PORT": "7701",
            "DB_PATH": "/tmp/x.db",
            "CORS_ORIGIN": "http://localhost:4000",
            "REPLAY_TEST_ID": "12",
        }
    )
    assert c.sensor_source == "replay"
    assert (c.sim.tremor_amp, c.sim.noise, c.sim.hand_mm, c.sim.reach_wobble) == (
        0.5,
        0.1,
        250.0,
        6.0,
    )
    assert (c.board_host, c.board_port) == ("10.0.0.2", 7701)
    assert c.db_path == Path("/tmp/x.db")
    assert c.cors_origin == "http://localhost:4000" and c.replay_test_id == 12


def test_load_config_rejects_bad_source() -> None:
    with pytest.raises(ValueError):
        load_config({"SENSOR_SOURCE": "wifi"})


def test_load_config_rejects_non_numeric() -> None:
    with pytest.raises(ValueError):
        load_config({"SIM_TREMOR_HZ": "fast"})
