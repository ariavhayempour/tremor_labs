"""JSON-safe codec for running analysis on the board: request args and results as plain dicts."""

import dataclasses
from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray

from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.posture import analyze_posture
from tremorlab.analysis.reach import ReachAttempt, ReachResult, analyze_reach
from tremorlab.analysis.tremor import TremorResult, analyze_tremor

OPS = ("tremor", "posture", "reach")
BAD_REQUEST = "bad_request"
INTERNAL = "internal"


def _plain(v: Any) -> Any:
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


def _arr(v: Any) -> NDArray[np.float64]:
    return np.asarray(v, dtype=np.float64)


def encode_args(**kw: Any) -> dict[str, Any]:
    """ndarrays and tuples become lists; units are whatever the analysis call expects."""
    return {k: _plain(v) for k, v in kw.items()}


def encode_result(r: TremorResult | ReachResult) -> dict[str, Any]:
    """Dataclass fields as JSON-safe values; ReachResult.attempts become a list of dicts."""
    if isinstance(r, ReachResult):
        return {
            "smoothness_mm": r.smoothness_mm,
            "wobble_ratio": r.wobble_ratio,
            "attempts": [
                {f.name: _plain(getattr(a, f.name)) for f in dataclasses.fields(a)}
                for a in r.attempts
            ],
        }
    return {f.name: _plain(getattr(r, f.name)) for f in dataclasses.fields(r)}


def decode_tremor(d: dict[str, Any]) -> TremorResult:
    return TremorResult(
        peak_hz=None if d["peak_hz"] is None else float(d["peak_hz"]),
        strength_ms2=float(d["strength_ms2"]),
        strength_score=float(d["strength_score"]),
        tremor_detected=bool(d["tremor_detected"]),
        freqs=_arr(d["freqs"]),
        psd=_arr(d["psd"]),
        valid_seconds=float(d["valid_seconds"]),
    )


def decode_reach(d: dict[str, Any]) -> ReachResult:
    attempts = [
        ReachAttempt(
            t=_arr(a["t"]),
            mm=_arr(a["mm"]),
            smoothed=_arr(a["smoothed"]),
            residual=_arr(a["residual"]),
            smoothness_mm=float(a["smoothness_mm"]),
            wobble_ratio=float(a["wobble_ratio"]),
        )
        for a in d["attempts"]
    ]
    return ReachResult(
        smoothness_mm=float(d["smoothness_mm"]),
        wobble_ratio=float(d["wobble_ratio"]),
        attempts=attempts,
    )


def _tremor(a: dict[str, Any]) -> TremorResult:
    return analyze_tremor(_arr(a["t"]), _arr(a["acc"]), trim=bool(a.get("trim", True)))


def _posture(a: dict[str, Any]) -> TremorResult:
    lo, hi = a["band"]
    return analyze_posture(
        _arr(a["t"]), _arr(a["acc"]), _arr(a["t_tof"]), _arr(a["mm"]), (float(lo), float(hi))
    )


def _reach(a: dict[str, Any]) -> ReachResult:
    return analyze_reach(_arr(a["t"]), _arr(a["mm"]), [float(m) for m in a["marks"]])


_HANDLERS: dict[str, Callable[[dict[str, Any]], TremorResult | ReachResult]] = {
    "tremor": _tremor,
    "posture": _posture,
    "reach": _reach,
}


def run_op(op: Any, args: Any) -> dict[str, Any]:
    """Board-side dispatch: run one analysis and return the response dict (never raises)."""
    handler = _HANDLERS.get(op) if isinstance(op, str) else None
    if handler is None or not isinstance(args, dict):
        return {"ok": False, "error": BAD_REQUEST}
    try:
        return {"ok": True, "result": encode_result(handler(args))}
    except AnalysisError as e:
        return {"ok": False, "error": e.code}
    except (KeyError, TypeError, ValueError) as e:
        return {"ok": False, "error": BAD_REQUEST, "message": str(e)}
    except Exception as e:  # any other failure is reported, so the Mac can fall back
        return {"ok": False, "error": INTERNAL, "message": repr(e)}
