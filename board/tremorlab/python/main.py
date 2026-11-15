# Relay (Bridge batches -> NDJSON on TCP 7700, LED lines -> Bridge.call) plus the analysis server on 7701.
import json
import os
import queue
import socket
import sys
import threading

# numpy + scipy are unpacked here by `make board-deploy`; first on the path, before anything imports numpy.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

from arduino.app_utils import *  # noqa: E402

import analysis_server  # noqa: E402

PORT = 7700
ANALYSIS_PORT = 7701
SEND_TIMEOUT_S = 1.0
LED_CALL_TIMEOUT_S = 2
LED_QUEUE_MAX = 32
logger = Logger("tremorlab")

_lock = threading.Lock()
_client = None
_led_queue = queue.Queue(maxsize=LED_QUEUE_MAX)


def _drop(conn):
    global _client
    with _lock:
        if _client is conn:
            _client = None
    try:
        conn.close()
    except OSError:
        pass


def _send(obj):
    line = (json.dumps(obj, separators=(",", ":")) + "\n").encode()
    with _lock:
        conn = _client
    if conn is None:
        return  # no Mac connected: drop, never buffer
    try:
        conn.sendall(line)
    except OSError:
        _drop(conn)


def _read_commands(conn):
    buf = b""
    while True:
        try:
            chunk = conn.recv(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if isinstance(msg, dict) and msg.get("k") == "led":
                try:
                    _led_queue.put_nowait((str(msg.get("cmd", "")), int(msg.get("value") or 0)))
                except (queue.Full, ValueError, TypeError):
                    pass
    _drop(conn)


def _serve():
    global _client
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(1)
    logger.info(f"listening on 0.0.0.0:{PORT}")
    while True:
        conn, addr = srv.accept()
        conn.settimeout(SEND_TIMEOUT_S)
        with _lock:
            old, _client = _client, conn
        if old is not None:
            try:
                old.close()
            except OSError:
                pass
        logger.info(f"client connected from {addr}")
        threading.Thread(target=_read_commands, args=(conn,), daemon=True).start()


def _led_worker():
    # Bridge.call runs here, never inside a Bridge callback.
    while True:
        cmd, value = _led_queue.get()
        try:
            Bridge.call("led", cmd, value, timeout=LED_CALL_TIMEOUT_S)
        except Exception as e:
            logger.warning(f"led {cmd} {value} failed: {e}")


def on_imu(d: list):
    _send({"k": "imu", "d": d})


def on_tof(d: list):
    _send({"k": "tof", "d": d})


STATUS_TEXT = {0: "ok", 1: "movement_missing", 2: "distance_missing", 3: "both_missing"}


def on_status(code: int, imu_count: int, tof_count: int, nan_count: int):
    _send({"k": "status", "d": [STATUS_TEXT.get(code, "unknown"), imu_count, tof_count, nan_count]})


Bridge.provide("imu", on_imu)
Bridge.provide("tof", on_tof)
Bridge.provide("status", on_status)
threading.Thread(target=_serve, daemon=True).start()
threading.Thread(target=_led_worker, daemon=True).start()
analysis_server.start(ANALYSIS_PORT, logger.info)
App.run()
