from pathlib import Path

from fastapi.testclient import TestClient

from tremorlab.config import load_config
from tremorlab.main import create_app


def test_get_sim_returns_params(client: TestClient) -> None:
    r = client.get("/api/sim")
    assert r.status_code == 200
    assert r.json() == {
        "tremor_hz": 5.0,
        "tremor_amp": 0.3,
        "noise": 0.02,
        "hand_mm": 200.0,
        "reach_wobble": 0.0,
    }


def test_put_sim_updates_frequency(client: TestClient) -> None:
    r = client.put("/api/sim", json={"tremor_hz": 7})
    assert r.status_code == 200 and r.json()["tremor_hz"] == 7
    assert client.get("/api/sim").json()["tremor_hz"] == 7


def test_put_sim_partial_keeps_other_fields(client: TestClient) -> None:
    body = client.put("/api/sim", json={"hand_mm": 150, "noise": 0.05}).json()
    assert body["hand_mm"] == 150 and body["noise"] == 0.05 and body["tremor_hz"] == 5.0


def test_put_sim_descent_action(client: TestClient) -> None:
    r = client.put("/api/sim", json={"action": "descent"})
    assert r.status_code == 200 and r.json()["tremor_hz"] == 5.0


def test_put_sim_rejects_out_of_range(client: TestClient) -> None:
    r = client.put("/api/sim", json={"tremor_hz": 0})
    assert r.status_code == 422 and r.json()["error"] == "validation_error"


def test_sim_routes_absent_for_board_source(tmp_path: Path) -> None:
    app = create_app(load_config({"SENSOR_SOURCE": "board", "DB_PATH": str(tmp_path / "t.db")}))
    c = TestClient(app)  # no lifespan: the board source isn't built yet
    for r in (c.get("/api/sim"), c.put("/api/sim", json={"tremor_hz": 7})):
        assert r.status_code in (404, 405)
        assert r.json()["error"] in ("not_found", "http_405")
    assert c.get("/api/sim").status_code == 404
