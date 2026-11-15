"""Hardware checklist: adb → device → forward → relay → status → sensors → rates → analysis."""

import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

RELAY_HOST = "127.0.0.1"
RELAY_PORT = 7700
ANALYSIS_PORT = 7701
ANALYSIS_TIMEOUT_S = 5.0
PROBE_FS_HZ = 100
PROBE_SAMPLES = 400
CONNECT_TIMEOUT_S = 2.0
READ_WINDOW_S = 3.0  # wall time to listen; a status line is sent once a second
MIN_RATE_SPAN_S = 2.0  # MCU time needed before rates are judged
IMU_HZ_RANGE = (90.0, 110.0)
TOF_HZ_RANGE = (25.0, 55.0)
BUNDLED_ADB_GLOB = "~/Library/Arduino15/packages/arduino/tools/adb/*/adb"
STATUS_SENSORS = {
    "ok": (True, True),
    "movement_missing": (False, True),
    "distance_missing": (True, False),
    "both_missing": (False, False),
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool | None  # None = skipped because an earlier check failed
    detail: str
    hint: str = ""


def _bundled_adb() -> list[str]:
    return sorted(glob.glob(os.path.expanduser(BUNDLED_ADB_GLOB)))


def check_adb(
    which: Callable[[str], str | None], bundled: Callable[[], list[str]]
) -> tuple[CheckResult, str | None]:
    path = which("adb") or (bundled() or [None])[-1]
    if path:
        return CheckResult("adb", True, path), path
    return CheckResult(
        "adb",
        False,
        "adb not found on PATH or in the App Lab install",
        "Install App Lab (it bundles adb) or run `brew install android-platform-tools`.",
    ), None


def check_device(adb: str, run: Callable[..., subprocess.CompletedProcess[str]]) -> CheckResult:
    out = run([adb, "devices"], capture_output=True, text=True, timeout=10).stdout
    rows = [line.split("\t") for line in out.splitlines()[1:] if "\t" in line]
    if any(state == "device" for _, state in rows):
        return CheckResult("device", True, ", ".join(serial for serial, _ in rows))
    if rows:
        states = ", ".join(f"{s}={st}" for s, st in rows)
        return CheckResult(
            "device",
            False,
            states,
            "Re-plug the USB-C cable and accept any prompt. "
            "Quit App Lab: it competes for the USB link.",
        )
    return CheckResult(
        "device",
        False,
        "no device listed",
        "Plug the UNO Q in with a USB-C data cable (not charge-only) "
        "and wait about 40 s for it to boot.",
    )


def check_forward(adb: str, run: Callable[..., subprocess.CompletedProcess[str]]) -> CheckResult:
    out = run([adb, "forward", "--list"], capture_output=True, text=True, timeout=10).stdout
    if f"tcp:{RELAY_PORT}" in out:
        return CheckResult("forward", True, out.strip())
    return CheckResult("forward", False, "no forward for port 7700", "Run `make board-link`.")


def read_relay(sock: Any, seconds: float) -> list[dict[str, Any]]:
    """Collect relay messages until a status line and enough MCU time arrive, or `seconds` pass."""
    sock.settimeout(0.5)
    deadline = time.monotonic() + seconds
    buf, msgs = b"", []
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(65536)
        except TimeoutError:
            continue
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if isinstance(msg, dict):
                msgs.append(msg)
        if any(m.get("k") == "status" for m in msgs) and _span(msgs, "imu", 7) >= MIN_RATE_SPAN_S:
            break
    return msgs


def _times(msgs: Sequence[dict[str, Any]], kind: str, stride: int) -> list[float]:
    """MCU sample times in s, unwrapped from signed 32-bit micros() and sorted."""
    raw = [
        int(m["d"][i]) & 0xFFFFFFFF
        for m in msgs
        if m.get("k") == kind
        for i in range(0, len(m["d"]), stride)
    ]
    if not raw:
        return []
    out, offset, prev = [], 0, raw[0]
    for t in raw:
        step = (t - prev) % 2**32
        offset += step if step < 2**31 else step - 2**32
        out.append(offset / 1e6)
        prev = t
    return sorted(out)


def _span(msgs: Sequence[dict[str, Any]], kind: str, stride: int) -> float:
    t = _times(msgs, kind, stride)
    return t[-1] - t[0] if len(t) > 1 else 0.0


def _rate(msgs: Sequence[dict[str, Any]], kind: str, stride: int) -> float | None:
    t = _times(msgs, kind, stride)
    return (len(t) - 1) / (t[-1] - t[0]) if len(t) > 1 and t[-1] > t[0] else None


def check_status(msgs: Sequence[dict[str, Any]]) -> tuple[CheckResult, str | None]:
    statuses = [m["d"][0] for m in msgs if m.get("k") == "status" and m.get("d")]
    if statuses:
        return CheckResult("status", True, f"latest: {statuses[-1]}"), str(statuses[-1])
    return CheckResult(
        "status",
        False,
        f"no status line within {READ_WINDOW_S:.0f} s ({len(msgs)} other lines)",
        "Start the app (see board/README.md). If it runs but sends nothing, power-cycle the board "
        "(the Bridge router can lose sync after many flashes).",
    ), None


def check_sensors(state: str) -> CheckResult:
    movement, distance = STATUS_SENSORS.get(state, (False, False))
    missing = [name for name, ok in (("movement", movement), ("distance", distance)) if not ok]
    if not missing:
        return CheckResult("sensors", True, "movement and distance present")
    return CheckResult(
        "sensors",
        False,
        f"missing: {', '.join(missing)} (status {state!r})",
        "Check the Qwiic chain: board → Modulino Distance → Modulino Movement, plugs fully seated. "
        "Then restart the app so the sketch re-detects them.",
    )


def check_rates(msgs: Sequence[dict[str, Any]]) -> CheckResult:
    imu, tof = _rate(msgs, "imu", 7), _rate(msgs, "tof", 2)
    detail = f"IMU {imu or 0:.1f} Hz, ToF {tof or 0:.1f} Hz"
    imu_ok = imu is not None and IMU_HZ_RANGE[0] <= imu <= IMU_HZ_RANGE[1]
    tof_ok = tof is not None and TOF_HZ_RANGE[0] <= tof <= TOF_HZ_RANGE[1]
    if imu_ok and tof_ok:
        return CheckResult("rates", True, detail)
    lo_i, hi_i = IMU_HZ_RANGE
    lo_t, hi_t = TOF_HZ_RANGE
    hint = (
        f"Expected IMU {lo_i:.0f}-{hi_i:.0f} Hz and ToF {lo_t:.0f}-{hi_t:.0f} Hz. Reflash "
        "board/tremorlab; a low IMU rate usually means Bridge batches are too large."
    )
    return CheckResult("rates", False, detail, hint)


def probe_analysis(host: str = RELAY_HOST, port: int = ANALYSIS_PORT) -> dict[str, Any]:
    """Send a 4 s still-hand tremor request to the board's analysis server; returns the response."""
    t = [i / PROBE_FS_HZ for i in range(PROBE_SAMPLES)]
    acc = [[0.0, 0.0, 9.80665]] * PROBE_SAMPLES
    req = {"op": "tremor", "args": {"t": t, "acc": acc, "trim": False}}
    with socket.create_connection((host, port), timeout=ANALYSIS_TIMEOUT_S) as sock:
        sock.sendall((json.dumps(req) + "\n").encode())
        with sock.makefile("rb") as f:
            resp: dict[str, Any] = json.loads(f.readline())
    return resp


def check_analysis(probe: Callable[[], dict[str, Any]]) -> CheckResult:
    hint = "Run `make board-link` (forwards 7701) and `make board-deploy`, then check app logs."
    start = time.monotonic()
    try:
        resp = probe()
    except (OSError, ValueError) as e:
        return CheckResult("analysis", False, f"no answer on port {ANALYSIS_PORT}: {e}", hint)
    ms = (time.monotonic() - start) * 1000
    if resp.get("ok") is True:
        return CheckResult("analysis", True, f"board analyzed a test signal in {ms:.0f} ms")
    return CheckResult("analysis", False, f"board error: {resp.get('error')}", hint)


def run_checks(
    which: Callable[[str], str | None] = shutil.which,
    bundled: Callable[[], list[str]] = _bundled_adb,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    connect: Callable[..., Any] = socket.create_connection,
    probe: Callable[[], dict[str, Any]] = probe_analysis,
) -> list[CheckResult]:
    names = ["adb", "device", "forward", "relay", "status", "sensors", "rates", "analysis"]
    results: list[CheckResult] = []

    def finish() -> list[CheckResult]:
        done = {r.name for r in results}
        return results + [CheckResult(n, None, "skipped") for n in names if n not in done]

    adb_result, adb = check_adb(which, bundled)
    results.append(adb_result)
    if adb is None:
        return finish()
    for check in (check_device, check_forward):
        results.append(check(adb, run))
        if not results[-1].ok:
            return finish()
    try:
        sock = connect((RELAY_HOST, RELAY_PORT), timeout=CONNECT_TIMEOUT_S)
    except OSError as e:
        results.append(
            CheckResult(
                "relay",
                False,
                f"cannot connect to {RELAY_HOST}:{RELAY_PORT}: {e}",
                "Start the tremorlab app on the board (see board/README.md).",
            )
        )
        return finish()
    try:
        msgs = read_relay(sock, READ_WINDOW_S)
    finally:
        sock.close()
    if not msgs:
        results.append(
            CheckResult(
                "relay",
                False,
                "connected, but no data arrived",
                "Start the tremorlab app on the board (see board/README.md); "
                "power-cycle the board if it is running.",
            )
        )
        return finish()
    results.append(CheckResult("relay", True, f"{len(msgs)} lines received"))
    status_result, state = check_status(msgs)
    results.append(status_result)
    if state is None:
        return finish()
    results.append(check_sensors(state))
    results.append(check_rates(msgs))
    results.append(check_analysis(probe))
    return finish()


def exit_code(results: Sequence[CheckResult]) -> int:
    return 0 if all(r.ok for r in results) else 1


def main() -> int:
    print("Note: this borrows the board relay for a few seconds; a running backend reconnects.")
    results = run_checks()
    for r in results:
        label = "PASS" if r.ok else ("SKIP" if r.ok is None else "FAIL")
        print(f"{label}  {r.name:<8} {r.detail}")
        if r.ok is False and r.hint:
            print(f"      fix: {r.hint}")
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
