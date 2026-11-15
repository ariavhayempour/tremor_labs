import importlib.util
import json
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "doctor.py"


def load_doctor() -> ModuleType:
    spec = importlib.util.spec_from_file_location("doctor", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


doctor = load_doctor()


def fake_run(outputs: dict[str, str]) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(args: Sequence[str], **_: Any) -> subprocess.CompletedProcess[str]:
        key = " ".join(args[1:])
        return subprocess.CompletedProcess(list(args), 0, stdout=outputs.get(key, ""), stderr="")

    return run


def relay_lines(
    imu_hz: float = 100.0, tof_hz: float = 50.0, seconds: float = 3.0, state: str = "ok"
) -> bytes:
    out: list[str] = []
    t0 = 4_294_000_000  # crosses the 32-bit wrap to exercise unwrapping
    for i in range(int(imu_hz * seconds)):
        t = (t0 + int(i * 1e6 / imu_hz)) & 0xFFFFFFFF
        t = t - 2**32 if t >= 2**31 else t  # the board sends signed int32
        out.append(json.dumps({"k": "imu", "d": [t, 0, 0, 1000, 0, 0, 0]}))
    for i in range(int(tof_hz * seconds)):
        t = (t0 + int(i * 1e6 / tof_hz)) & 0xFFFFFFFF
        t = t - 2**32 if t >= 2**31 else t
        out.append(json.dumps({"k": "tof", "d": [t, 200]}))
    out.append(json.dumps({"k": "status", "d": [state, 100, 50, 0]}))
    return ("\n".join(out) + "\n").encode()


class FakeSock:
    def __init__(self, data: bytes) -> None:
        self.chunks = [data[i : i + 4096] for i in range(0, len(data), 4096)]

    def settimeout(self, _: float) -> None: ...

    def recv(self, _: int) -> bytes:
        return self.chunks.pop(0) if self.chunks else b""

    def close(self) -> None: ...


ADB_OK = {
    "devices": "List of devices attached\n4061194084\tdevice\n\n",
    "forward --list": "4061194084 tcp:7700 tcp:7700\n",
}


def run_doctor(**kw: Any) -> list[Any]:
    defaults: dict[str, Any] = {
        "which": lambda _: "/usr/bin/adb",
        "bundled": lambda: [],
        "run": fake_run(ADB_OK),
        "connect": lambda *_a, **_k: FakeSock(relay_lines()),
    }
    defaults.update(kw)
    return doctor.run_checks(**defaults)


def test_doctor_reports_missing_adb_with_hint() -> None:
    results = run_doctor(which=lambda _: None, bundled=lambda: [])
    assert results[0].name == "adb" and results[0].ok is False
    assert "android-platform-tools" in results[0].hint
    assert all(r.ok is None for r in results[1:])  # later checks are skipped
    assert doctor.exit_code(results) == 1


def test_doctor_uses_app_lab_bundled_adb() -> None:
    results = run_doctor(which=lambda _: None, bundled=lambda: ["/x/adb/32.0.0/adb"])
    assert results[0].ok is True and "/x/adb/32.0.0/adb" in results[0].detail


def test_doctor_all_pass_exit_zero() -> None:
    results = run_doctor()
    assert [r.name for r in results] == [
        "adb",
        "device",
        "forward",
        "relay",
        "status",
        "sensors",
        "rates",
    ]
    assert all(r.ok for r in results), [(r.name, r.detail) for r in results]
    assert doctor.exit_code(results) == 0


def test_doctor_unauthorized_device_hint() -> None:
    results = run_doctor(
        run=fake_run({**ADB_OK, "devices": "List of devices attached\nX\tunauthorized\n"})
    )
    device = results[1]
    assert (
        device.ok is False and "unauthorized" in device.detail and "re-plug" in device.hint.lower()
    )


def test_doctor_missing_forward_hint() -> None:
    results = run_doctor(run=fake_run({**ADB_OK, "forward --list": ""}))
    assert results[2].ok is False and "make board-link" in results[2].hint


def test_doctor_relay_refused_hint() -> None:
    def refuse(*_a: Any, **_k: Any) -> Any:
        raise ConnectionRefusedError

    results = run_doctor(connect=refuse)
    assert results[3].ok is False and "tremorlab" in results[3].hint


def test_doctor_missing_sensor_reported() -> None:
    results = run_doctor(connect=lambda *_a, **_k: FakeSock(relay_lines(state="distance_missing")))
    sensors = results[5]
    assert sensors.ok is False and "distance" in sensors.detail and "Qwiic" in sensors.hint


@pytest.mark.parametrize(("imu_hz", "tof_hz"), [(60.0, 50.0), (100.0, 10.0)])
def test_doctor_rate_out_of_range_fails(imu_hz: float, tof_hz: float) -> None:
    results = run_doctor(
        connect=lambda *_a, **_k: FakeSock(relay_lines(imu_hz=imu_hz, tof_hz=tof_hz))
    )
    assert results[6].ok is False


def test_doctor_no_status_line_fails() -> None:
    data = b"".join(line + b"\n" for line in relay_lines().splitlines() if b'"status"' not in line)
    results = run_doctor(connect=lambda *_a, **_k: FakeSock(data))
    assert results[4].ok is False and "power-cycle" in results[4].hint.lower()
