from fastapi.testclient import TestClient

from tremorlab.api.errors import ApiError
from tremorlab.config import Config
from tremorlab.main import create_app


def test_health_reports_source(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["sensor_source"] == "sim"


def test_health_shape(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert set(body) == {
        "status",
        "sensor_source",
        "connected",
        "sensors_detected",
        "imu_hz",
        "tof_hz",
    }
    assert body["status"] == "ok"
    assert set(body["sensors_detected"]) == {"movement", "distance"}


def test_cors_allows_frontend_origin(client: TestClient) -> None:
    r = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_validation_errors_use_error_shape(client: TestClient) -> None:
    r = client.post("/api/checks", json={"medication": "sometimes"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "validation_error" and isinstance(body["message"], str)


def test_api_error_uses_error_shape(config: Config) -> None:
    app = create_app(config)

    @app.get("/_conflict")
    def conflict() -> None:
        raise ApiError(409, "test_active", "A test is already recording.")

    with TestClient(app) as c:
        r = c.get("/_conflict")
    assert r.status_code == 409
    assert r.json() == {"error": "test_active", "message": "A test is already recording."}
