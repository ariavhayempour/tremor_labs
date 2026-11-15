"""Print ~3 s of simulator /ws messages as a JSON array (source for frontend ws_stream.json)."""

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from tremorlab.config import load_config
from tremorlab.main import create_app

WARMUP_S = 5.0  # the live spectrum needs at least 4 s of recorded data


def start_rest(client: TestClient) -> int | None:
    """Start a rest test so spectrum/status messages flow; None if those endpoints aren't built."""
    check = client.post("/api/checks", json={"medication": "not_yet"})
    if check.status_code != 201:
        return None
    test = client.post(
        f"/api/checks/{check.json()['check_id']}/tests", json={"type": "rest", "hand": "right"}
    )
    return int(test.json()["test_id"]) if test.status_code == 201 else None


def read_for(ws: WebSocketTestSession, seconds: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        out.append(ws.receive_json())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--tremor-hz", type=float, default=5.0)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        env = {"SIM_TREMOR_HZ": str(args.tremor_hz), "DB_PATH": str(Path(tmp) / "dump.db")}
        try:
            with (
                TestClient(create_app(load_config(env))) as client,
                client.websocket_connect("/ws") as ws,
            ):
                test_id = start_rest(client)
                if test_id is None:
                    print("check/test endpoints unavailable: stream only", file=sys.stderr)
                else:
                    read_for(ws, WARMUP_S)
                messages = read_for(ws, args.seconds)
                if test_id is not None:
                    client.post(f"/api/tests/{test_id}/stop")
        except WebSocketDisconnect as e:
            print(f"/ws closed ({e.code}): the stream isn't available yet", file=sys.stderr)
            return 1
    json.dump(messages, sys.stdout)
    print(file=sys.stderr)
    print(f"{len(messages)} messages", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
