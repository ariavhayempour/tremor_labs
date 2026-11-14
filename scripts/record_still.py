"""Record IMU acceleration from the backend's /ws to an .npz (t: epoch s, acc: (N, 3) m/s²)."""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from websockets.sync.client import connect


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="ws://localhost:8000/ws")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    t_parts: list[np.ndarray] = []
    acc_parts: list[np.ndarray] = []
    with connect(args.url, open_timeout=3) as ws:
        print(f"recording {args.seconds:.0f} s ...", flush=True)
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            try:
                msg = json.loads(ws.recv(timeout=1.0))
            except TimeoutError:
                continue
            if msg.get("type") != "imu" or not msg["samples"]:
                continue
            samples = np.asarray(msg["samples"], dtype=np.float64)
            t_parts.append(msg["t0"] + np.arange(len(samples)) / msg["fs"])
            acc_parts.append(samples[:, :3])
    if not t_parts:
        print("no IMU data received (is the backend running with a live source?)")
        return 1
    t = np.concatenate(t_parts)
    acc = np.concatenate(acc_parts)
    order = np.argsort(t, kind="stable")
    t, acc = t[order], acc[order]
    keep = np.concatenate([[True], np.diff(t) > 0])
    t, acc = t[keep], acc[keep]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, t=t, acc=acc)
    fs = float(np.median(1 / np.diff(t))) if len(t) > 1 else 0.0
    print(f"saved {len(t)} samples ({t[-1] - t[0]:.1f} s, median {fs:.1f} Hz) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
