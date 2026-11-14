import json
import socket
import threading

from arduino.app_utils import *

PORT = 7700
logger = Logger("tremor-probe-throughput")
_lock = threading.Lock()
_client = None


def _serve():
    global _client
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(1)
    logger.info(f"listening on 0.0.0.0:{PORT}")
    while True:
        conn, addr = srv.accept()
        with _lock:
            if _client is not None:
                _client.close()
            _client = conn
        logger.info(f"client connected from {addr}")


def _send(obj):
    global _client
    line = (json.dumps(obj, separators=(",", ":")) + "\n").encode()
    with _lock:
        conn = _client
    if conn is None:
        return
    try:
        conn.sendall(line)
    except OSError:
        with _lock:
            if _client is conn:
                _client = None
        conn.close()


_phase = {"size": None, "got": 0, "bad_len": 0}


def on_phase(size: int):
    prev = dict(_phase)
    if prev["size"] is not None:
        _send({"k": "summary", "size": prev["size"], "got": prev["got"], "expected": 30, "bad_len": prev["bad_len"]})
    _phase.update(size=size, got=0, bad_len=0)


def on_vec(d: list):
    _phase["got"] += 1
    if len(d) != _phase["size"]:
        _phase["bad_len"] += 1


Bridge.provide("phase", on_phase)
Bridge.provide("vec", on_vec)
threading.Thread(target=_serve, daemon=True).start()
App.run()
