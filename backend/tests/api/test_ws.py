from fastapi.testclient import TestClient


def test_ws_streams_imu_and_tof(client: TestClient) -> None:
    seen: set[str] = set()
    with client.websocket_connect("/ws") as ws:
        for _ in range(30):
            seen.add(ws.receive_json()["type"])
            if {"imu", "tof"} <= seen:
                break
    assert {"imu", "tof"} <= seen


def test_ws_sends_source_message_first(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
    assert first["type"] == "source" and first["sensor_source"] == "sim"
    assert set(first) == {"type", "sensor_source", "connected", "sensors", "imu_hz", "tof_hz"}


def test_ws_imu_message_matches_contract(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        while (m := ws.receive_json())["type"] != "imu":
            pass
    assert set(m) == {"type", "t0", "fs", "samples"}
    assert abs(m["fs"] - 100.0) < 1 and len(m["samples"][0]) == 6


def test_health_reads_live_source(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        for _ in range(12):
            ws.receive_json()
    body = client.get("/api/health").json()
    assert body["connected"] is True and body["sensor_source"] == "sim"
    assert body["imu_hz"] is not None and abs(body["imu_hz"] - 100.0) < 1.0
