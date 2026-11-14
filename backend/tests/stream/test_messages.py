import json

import numpy as np
import pytest

from tremorlab.sources.base import ImuBatch, SourceHealth, TofBatch
from tremorlab.stream.messages import (
    imu_msg,
    position_msg,
    source_msg,
    spectrum_msg,
    status_msg,
    tof_msg,
)


def imu_batch(fs: float = 100.0, n: int = 10, t0: float = 1_800_000_000.0) -> ImuBatch:
    t = t0 + np.arange(n) / fs
    acc = np.tile([0.1, 0.2, 9.81], (n, 1))
    gyro = np.tile([1.0, 2.0, 3.0], (n, 1))
    return ImuBatch(t=t, acc=acc, gyro=gyro)


def test_imu_msg_shape() -> None:
    m = imu_msg(imu_batch())
    assert m["type"] == "imu" and len(m["samples"][0]) == 6 and abs(m["fs"] - 100) < 1
    assert m["t0"] == pytest.approx(1_800_000_000.0)
    assert m["samples"][0] == pytest.approx([0.1, 0.2, 9.81, 1.0, 2.0, 3.0])
    json.dumps(m, allow_nan=False)


def test_imu_msg_fs_is_measured_not_assumed() -> None:
    assert imu_msg(imu_batch(fs=97.0))["fs"] == pytest.approx(97.0)


def test_imu_msg_single_sample_uses_fallback_fs() -> None:
    assert imu_msg(imu_batch(n=1), fallback_fs=98.0)["fs"] == 98.0
    assert imu_msg(imu_batch(n=1))["fs"] > 0


def test_tof_msg_drops_nan_samples() -> None:
    t = 1_800_000_000.0 + np.arange(4) / 40.0
    m = tof_msg(TofBatch(t=t, mm=np.array([np.nan, 201.0, 202.0, 203.0])))
    assert m["type"] == "tof" and m["samples_mm"] == [201.0, 202.0, 203.0]
    assert m["t0"] == pytest.approx(t[1]) and m["fs"] == pytest.approx(40.0)
    json.dumps(m, allow_nan=False)


def test_tof_msg_all_invalid_is_empty() -> None:
    t = np.arange(2) / 40.0
    m = tof_msg(TofBatch(t=t, mm=np.array([np.nan, np.nan])))
    assert m["samples_mm"] == []
    json.dumps(m, allow_nan=False)


def test_spectrum_msg_cuts_at_15hz_and_rounds() -> None:
    freqs = np.arange(0, 50.25, 0.25)
    psd = np.full(freqs.shape, 0.123456789)
    m = spectrum_msg(freqs, psd, 5.0)
    assert m["type"] == "spectrum" and m["peak_hz"] == 5.0
    assert max(m["freqs"]) == 15.0 and len(m["freqs"]) == len(m["psd"]) == 61
    assert m["psd"][0] == 0.1235
    assert spectrum_msg(freqs, psd, None)["peak_hz"] is None


def test_position_msg_shape() -> None:
    m = position_msg(214.0, True, (170.0, 230.0), 12.5)
    assert m == {
        "type": "position",
        "tof_mm": 214.0,
        "in_band": True,
        "band": [170.0, 230.0],
        "valid_seconds": 12.5,
    }
    assert position_msg(None, False, (170.0, 230.0), 0.0)["tof_mm"] is None


def test_status_msg_shape() -> None:
    assert status_msg(True, 40, "rest") == {
        "type": "status",
        "recording": True,
        "test_id": 40,
        "test_type": "rest",
        "seconds_left": None,
    }
    assert status_msg(False, None, None)["test_id"] is None


def test_source_msg_shape() -> None:
    health = SourceHealth(True, {"movement": True, "distance": False}, 100.2, None)
    assert source_msg(health, "board") == {
        "type": "source",
        "sensor_source": "board",
        "connected": True,
        "sensors": {"movement": True, "distance": False},
        "imu_hz": 100.2,
        "tof_hz": None,
    }
