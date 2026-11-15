import importlib
import json
import socket
import socketserver
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from tests.analysis.synth import descent_tof, sine_imu, tof_track
from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.posture import analyze_posture
from tremorlab.analysis.reach import analyze_reach
from tremorlab.analysis.tremor import analyze_tremor
from tremorlab.sources.board_analysis import board_analyzers

BOARD_PY = Path(__file__).resolve().parents[3] / "board" / "tremorlab" / "python"
BAND = (170.0, 230.0)


def _server_module() -> ModuleType:
    sys.path.insert(0, str(BOARD_PY))
    try:
        return importlib.import_module("analysis_server")
    finally:
        sys.path.remove(str(BOARD_PY))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@pytest.fixture
def board_server() -> Iterator[tuple[int, list[str]]]:
    lines: list[str] = []
    port = _free_port()
    srv: socketserver.TCPServer = _server_module().start(port, lines.append)
    yield port, lines
    srv.shutdown()
    srv.server_close()


def test_rest_runs_on_server_and_matches_local(board_server: tuple[int, list[str]]) -> None:
    port, lines = board_server
    t, acc = sine_imu(5.0, 0.3, 30)
    got = board_analyzers("127.0.0.1", port).tremor(t, acc)
    want = analyze_tremor(t, acc)
    assert got.peak_hz == want.peak_hz and got.strength_ms2 == want.strength_ms2
    np.testing.assert_array_equal(got.psd, want.psd)
    assert any(line.startswith("analyzed tremor n=3000") for line in lines)


def test_posture_and_reach_run_on_server(board_server: tuple[int, list[str]]) -> None:
    port, lines = board_server
    a = board_analyzers("127.0.0.1", port)
    t, acc = sine_imu(6.0, 0.3, 30)
    t_tof, mm = tof_track(30)
    mm[::17] = np.nan
    assert a.posture(t, acc, t_tof, mm, BAND).strength_ms2 == pytest.approx(
        analyze_posture(t, acc, t_tof, mm, BAND).strength_ms2, rel=0, abs=0
    )
    td, md = descent_tof()
    assert a.reach(td, md, []).smoothness_mm == analyze_reach(td, md, []).smoothness_mm
    assert [line.split()[1] for line in lines if line.startswith("analyzed")] == [
        "posture",
        "reach",
    ]


def test_analysis_error_from_board_is_raised_not_retried_locally(
    board_server: tuple[int, list[str]], caplog: pytest.LogCaptureFixture
) -> None:
    port, _ = board_server
    t, mm = tof_track(5)
    with pytest.raises(AnalysisError) as e:
        board_analyzers("127.0.0.1", port).reach(t, mm, [])
    assert e.value.code == "no_descent_detected"
    assert "analyzing on the Mac" not in caplog.text


def test_unreachable_board_falls_back_to_local(caplog: pytest.LogCaptureFixture) -> None:
    t, acc = sine_imu(5.0, 0.3, 10)
    got = board_analyzers("127.0.0.1", _free_port(), timeout_s=0.5).tremor(t, acc)
    assert got.strength_ms2 == analyze_tremor(t, acc).strength_ms2
    assert "board analysis unavailable, analyzing on the Mac" in caplog.text


def _one_shot_server(reply: bytes) -> tuple[int, threading.Thread]:
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port: int = srv.getsockname()[1]

    def serve() -> None:
        conn, _ = srv.accept()
        with conn:
            conn.makefile("rb").readline()
            conn.sendall(reply)
        srv.close()

    th = threading.Thread(target=serve, daemon=True)
    th.start()
    return port, th


@pytest.mark.parametrize(
    "reply",
    [
        json.dumps({"ok": False, "error": "internal", "message": "boom"}).encode() + b"\n",
        b'{"ok": true, "result": {"peak_hz": 5.0}}\n',
        b"not json\n",
        b'{"ok": true',
    ],
)
def test_board_failures_fall_back_to_local(reply: bytes, caplog: pytest.LogCaptureFixture) -> None:
    port, th = _one_shot_server(reply)
    t, acc = sine_imu(5.0, 0.3, 10)
    got = board_analyzers("127.0.0.1", port, timeout_s=1.0).tremor(t, acc)
    th.join(2)
    assert got.strength_ms2 == analyze_tremor(t, acc).strength_ms2
    assert "analyzing on the Mac" in caplog.text


def test_tap_stays_local() -> None:
    from tremorlab.analysis.tap import analyze_taps

    assert board_analyzers("127.0.0.1", 1).tap is analyze_taps
    assert board_analyzers("127.0.0.1", 1).remote is True


def test_only_the_board_source_analyzes_on_the_board() -> None:
    from tremorlab.config import load_config
    from tremorlab.main import default_analyzers_for

    assert default_analyzers_for(load_config({"SENSOR_SOURCE": "board"})).remote is True
    assert default_analyzers_for(load_config({"SENSOR_SOURCE": "sim"})).remote is False
    assert default_analyzers_for(load_config({"SENSOR_SOURCE": "replay"})).remote is False
