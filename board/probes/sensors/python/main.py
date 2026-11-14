import json
import socket
import threading

from arduino.app_utils import *

PORT = 7700
logger = Logger("tremor-probe-sensors")
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


def on_rates(imu_hz: int, tof_avail: int, tof_new: int, invalid_polls: int, loop_hz: int, movement_ok: int, distance_ok: int):
    _send({"k": "rates", "imu_hz": imu_hz, "tof_available_per_s": tof_avail, "tof_new_per_s": tof_new,
           "invalid_polls": invalid_polls, "loop_hz": loop_hz, "movement_ok": movement_ok, "distance_ok": distance_ok})


Bridge.provide("rates", on_rates)
threading.Thread(target=_serve, daemon=True).start()
App.run()
