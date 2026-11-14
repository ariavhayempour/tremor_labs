from fastapi.testclient import TestClient

from tremorlab.config import Config
from tremorlab.main import create_app
from tremorlab.sources.base import LedCommand


class RecordingSource:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[LedCommand, int | None]] = []
        self.fail = fail

    async def led(self, command: LedCommand, value: int | None) -> None:
        self.calls.append((command, value))
        if self.fail:
            raise ConnectionError("board unplugged")


def test_led_endpoint_calls_source(config: Config) -> None:
    app = create_app(config)
    fake = RecordingSource()
    with TestClient(app) as c:
        app.state.source = fake
        r = c.post("/api/led", json={"command": "countdown", "value": 7})
        r2 = c.post("/api/led", json={"command": "hold"})
    assert r.status_code == 204 and r2.status_code == 204
    assert fake.calls == [("countdown", 7), ("hold", None)]


def test_led_failure_is_swallowed(config: Config) -> None:
    app = create_app(config)
    with TestClient(app) as c:
        app.state.source = RecordingSource(fail=True)
        r = c.post("/api/led", json={"command": "check"})
    assert r.status_code == 204


def test_led_rejects_unknown_command(config: Config) -> None:
    with TestClient(create_app(config)) as c:
        r = c.post("/api/led", json={"command": "disco"})
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
