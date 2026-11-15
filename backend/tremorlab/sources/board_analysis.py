"""Analyzers that run on the UNO Q's analysis server, falling back to the same code locally."""

import json
import logging
import socket
from collections.abc import Callable
from typing import Any, TypeVar, get_args

import numpy as np
from numpy.typing import NDArray

from tremorlab.analysis import Analyzers
from tremorlab.analysis.errors import AnalysisError, AnalysisErrorCode
from tremorlab.analysis.posture import analyze_posture
from tremorlab.analysis.reach import ReachResult, analyze_reach
from tremorlab.analysis.tap import analyze_taps
from tremorlab.analysis.tremor import TremorResult, analyze_tremor
from tremorlab.analysis.wire import decode_reach, decode_tremor, encode_args

BOARD_ANALYSIS_TIMEOUT_S = 3.0
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
ANALYSIS_CODES: frozenset[str] = frozenset(get_args(AnalysisErrorCode))

log = logging.getLogger(__name__)

R = TypeVar("R")
Arr = NDArray[np.float64]


class BoardAnalysisError(Exception):
    """The board could not run the request (unreachable, timed out, or an internal error)."""


def call_board(host: str, port: int, op: str, args: dict[str, Any], timeout_s: float) -> Any:
    """Send one request, return the decoded `result`; AnalysisError for analysis failures."""
    line = (json.dumps({"op": op, "args": args}, separators=(",", ":")) + "\n").encode()
    try:
        with socket.create_connection((host, port), timeout=timeout_s) as sock:
            sock.sendall(line)
            with sock.makefile("rb") as f:
                raw = f.readline(MAX_RESPONSE_BYTES)
    except OSError as e:
        raise BoardAnalysisError(f"{op}: {e}") from e
    if not raw.endswith(b"\n"):
        raise BoardAnalysisError(f"{op}: connection closed before a full response")
    try:
        resp = json.loads(raw)
    except ValueError as e:
        raise BoardAnalysisError(f"{op}: unreadable response") from e
    if not isinstance(resp, dict):
        raise BoardAnalysisError(f"{op}: unexpected response")
    if resp.get("ok") is True:
        return resp.get("result")
    code = resp.get("error")
    if code in ANALYSIS_CODES:
        raise AnalysisError(code, resp.get("message"))
    raise BoardAnalysisError(f"{op}: board error {code}: {resp.get('message', '')}")


def board_analyzers(host: str, port: int, timeout_s: float = BOARD_ANALYSIS_TIMEOUT_S) -> Analyzers:
    """Rest, posture and reach on the board; the tap test stays local (MediaPipe runs here)."""

    def remote(
        op: str, args: dict[str, Any], decode: Callable[[Any], R], local: Callable[[], R]
    ) -> R:
        try:
            return decode(call_board(host, port, op, args, timeout_s))
        except BoardAnalysisError as e:
            log.warning("board analysis unavailable, analyzing on the Mac: %s", e)
        except (KeyError, TypeError, ValueError) as e:
            log.warning("board analysis returned a malformed result, analyzing on the Mac: %r", e)
        return local()

    def tremor(t: Arr, acc: Arr, *, trim: bool = True) -> TremorResult:
        args = encode_args(t=t, acc=acc, trim=trim)
        return remote("tremor", args, decode_tremor, lambda: analyze_tremor(t, acc, trim=trim))

    def posture(
        t_imu: Arr, acc: Arr, t_tof: Arr, mm: Arr, band: tuple[float, float]
    ) -> TremorResult:
        args = encode_args(t=t_imu, acc=acc, t_tof=t_tof, mm=mm, band=band)
        return remote(
            "posture", args, decode_tremor, lambda: analyze_posture(t_imu, acc, t_tof, mm, band)
        )

    def reach(t: Arr, mm: Arr, marks: list[float]) -> ReachResult:
        args = encode_args(t=t, mm=mm, marks=list(marks))
        return remote("reach", args, decode_reach, lambda: analyze_reach(t, mm, marks))

    return Analyzers(tremor=tremor, posture=posture, reach=reach, tap=analyze_taps, remote=True)
