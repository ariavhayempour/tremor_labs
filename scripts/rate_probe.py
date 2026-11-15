"""Print measured IMU/ToF rates and end-to-end lag each second, read from the backend's /ws."""

import argparse
import json
import sys
import time

from websockets.sync.client import ClientConnection, connect


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="ws://localhost:8000/ws")
    ap.add_argument("--seconds", type=float, default=0.0, help="stop after N s (0 = until Ctrl-C)")
    args = ap.parse_args()
    try:
        ws = connect(args.url, open_timeout=3)
    except OSError as e:
        print(f"cannot connect to {args.url}: {e} (is `make dev` running?)")
        return 1
    with ws:
        return _stream(ws, args.seconds)


def _stream(ws: ClientConnection, seconds: float) -> int:
    start = tick = time.monotonic()
    imu_n = tof_n = 0
    lags: list[float] = []
    try:
        while not seconds or time.monotonic() - start < seconds:
            try:
                msg = json.loads(ws.recv(timeout=1.0))
            except TimeoutError:
                msg = {}
            if msg.get("type") == "imu" and msg["samples"]:
                imu_n += len(msg["samples"])
                newest = msg["t0"] + (len(msg["samples"]) - 1) / msg["fs"]
                lags.append(time.time() - newest)
            elif msg.get("type") == "tof":
                tof_n += len(msg["samples_mm"])
            elif msg.get("type") == "source":
                print(f"source: connected={msg['connected']} sensors={msg['sensors']}")
            now = time.monotonic()
            if now - tick >= 1.0:
                lag = f"{1000 * sorted(lags)[len(lags) // 2]:.0f} ms" if lags else "n/a"
                imu_hz, tof_hz = imu_n / (now - tick), tof_n / (now - tick)
                line = f"IMU {imu_hz:6.1f} Hz  ToF {tof_hz:5.1f} Hz  median lag {lag}"
                print(f"[{now - start:5.1f}s] {line}", flush=True)
                imu_n = tof_n = 0
                lags.clear()
                tick = now
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
