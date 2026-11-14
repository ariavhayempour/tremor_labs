import numpy as np
import pytest

from tremorlab.sources.base import ImuBatch, SourceStatus, TofBatch
from tremorlab.stream.recorder import Recorder


def imu(t0: float, n: int = 10) -> ImuBatch:
    t = t0 + np.arange(n) / 100.0
    return ImuBatch(t=t, acc=np.tile([0.0, 0.0, 9.81], (n, 1)), gyro=np.zeros((n, 3)))


def tof(t0: float, mm: list[float]) -> TofBatch:
    return TofBatch(t=t0 + np.arange(len(mm)) / 40.0, mm=np.array(mm))


def test_imu_and_tof_concatenate_in_order() -> None:
    r = Recorder(1, "rest", 0.0, None)
    r.add(imu(0.0))
    r.add(tof(0.0, [200.0, 201.0]))
    r.add(SourceStatus(connected=True))
    r.add(imu(0.1))
    t, acc = r.imu()
    assert len(t) == 20 and acc.shape == (20, 3) and t[10] == pytest.approx(0.1)
    tt, mm = r.tof()
    assert list(mm) == [200.0, 201.0] and len(tt) == 2


def test_empty_recorder_arrays() -> None:
    r = Recorder(1, "rest", 0.0, None)
    t, acc = r.imu()
    assert t.shape == (0,) and acc.shape == (0, 3)
    assert r.tof()[0].shape == (0,)
    assert r.latest_tof() is None


def test_imu_window_returns_last_seconds_of_recording() -> None:
    r = Recorder(1, "rest", 0.0, None)
    for k in range(100):
        r.add(imu(k / 10.0))
    t, acc = r.imu_window(8.0)
    assert len(t) == 800 and acc.shape == (800, 3)
    assert t[-1] == pytest.approx(9.99)


def test_raw_payloads_are_ws_messages_in_arrival_order() -> None:
    r = Recorder(1, "rest", 0.0, None)
    r.add(imu(0.0))
    r.add(tof(0.0, [200.0, float("nan"), 202.0]))
    r.add(tof(0.1, [float("nan")]))  # nothing valid: not stored
    r.add(imu(0.1))
    payloads = list(r.raw_payloads())
    assert [s for s, _ in payloads] == ["imu", "tof", "imu"]
    assert payloads[1][1]["samples_mm"] == [200.0, 202.0]
    assert payloads[0][1]["type"] == "imu" and len(payloads[0][1]["samples"]) == 10


def test_markers() -> None:
    r = Recorder(1, "reach", 0.0, None)
    r.mark(3.5)
    r.mark(7.0)
    assert r.markers == [3.5, 7.0]


def test_latest_tof_none_when_invalid() -> None:
    r = Recorder(1, "posture", 0.0, (170.0, 230.0))
    r.add(tof(0.0, [200.0, 201.0]))
    assert r.latest_tof() == 201.0
    r.add(tof(0.1, [float("nan")]))
    assert r.latest_tof() is None
    r.add(tof(0.2, [1500.0]))
    assert r.latest_tof() is None


def test_valid_seconds_accumulates_in_band_time_only() -> None:
    r = Recorder(1, "posture", 0.0, (170.0, 230.0))
    for k in range(10):  # 1 s in band
        r.add(tof(k * 0.1, [200.0] * 4))
    assert r.valid_seconds == pytest.approx(1.0 - 1 / 40, abs=1e-9)
    for k in range(10, 20):  # 1 s too high
        r.add(tof(k * 0.1, [300.0] * 4))
    before = r.valid_seconds
    for k in range(20, 30):  # 1 s invalid
        r.add(tof(k * 0.1, [float("nan")] * 4))
    assert r.valid_seconds == pytest.approx(before)
    for k in range(30, 40):
        r.add(tof(k * 0.1, [210.0] * 4))
    assert r.valid_seconds == pytest.approx(2.0 - 2 / 40, abs=1e-9)


def test_band_set_lazily_from_first_valid_reading() -> None:
    r = Recorder(1, "posture", 0.0, None, band_from=lambda mm: (mm - 30.0, mm + 30.0))
    r.add(tof(0.0, [float("nan")]))
    assert r.band is None
    r.add(tof(0.1, [250.0, 251.0]))
    assert r.band == (220.0, 280.0)
