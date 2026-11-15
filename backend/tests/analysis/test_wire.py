import json
from typing import Any

import numpy as np

from tests.analysis.synth import descent_tof, sine_imu, tof_track
from tremorlab.analysis.posture import analyze_posture
from tremorlab.analysis.reach import ReachResult, analyze_reach
from tremorlab.analysis.tremor import TremorResult, analyze_tremor
from tremorlab.analysis.wire import decode_reach, decode_tremor, encode_args, run_op

BAND = (170.0, 230.0)


def _over_wire(op: str, **kw: Any) -> dict[str, Any]:
    """Encode, run and decode exactly as the TCP path does, through json text both ways."""
    req = json.loads(json.dumps({"op": op, "args": encode_args(**kw)}))
    out: dict[str, Any] = json.loads(json.dumps(run_op(req["op"], req["args"])))
    return out


def _assert_tremor_equal(a: TremorResult, b: TremorResult) -> None:
    assert a.peak_hz == b.peak_hz
    assert a.strength_ms2 == b.strength_ms2
    assert a.strength_score == b.strength_score
    assert a.tremor_detected == b.tremor_detected
    assert a.valid_seconds == b.valid_seconds
    np.testing.assert_array_equal(a.freqs, b.freqs)
    np.testing.assert_array_equal(a.psd, b.psd)


def test_tremor_round_trip_matches_direct_call() -> None:
    t, acc = sine_imu(5.0, 0.3, 30)
    resp = _over_wire("tremor", t=t, acc=acc, trim=True)
    assert resp["ok"] is True
    _assert_tremor_equal(decode_tremor(resp["result"]), analyze_tremor(t, acc))


def test_tremor_untrimmed_live_window() -> None:
    t, acc = sine_imu(5.0, 0.3, 8)
    resp = _over_wire("tremor", t=t, acc=acc, trim=False)
    _assert_tremor_equal(decode_tremor(resp["result"]), analyze_tremor(t, acc, trim=False))


def test_posture_round_trip_with_nan_tof() -> None:
    t, acc = sine_imu(6.0, 0.3, 30)
    t_tof, mm = tof_track(30)
    mm[::17] = np.nan
    resp = _over_wire("posture", t=t, acc=acc, t_tof=t_tof, mm=mm, band=BAND)
    assert resp["ok"] is True
    _assert_tremor_equal(decode_tremor(resp["result"]), analyze_posture(t, acc, t_tof, mm, BAND))


def test_reach_round_trip_keeps_attempts() -> None:
    t, mm = descent_tof()
    mm[5] = np.nan
    resp = _over_wire("reach", t=t, mm=mm, marks=[])
    assert resp["ok"] is True
    got: ReachResult = decode_reach(resp["result"])
    want = analyze_reach(t, mm, [])
    assert got.smoothness_mm == want.smoothness_mm
    assert got.wobble_ratio == want.wobble_ratio
    assert len(got.attempts) == len(want.attempts) == 1
    np.testing.assert_array_equal(got.attempts[0].smoothed, want.attempts[0].smoothed)
    np.testing.assert_array_equal(got.attempts[0].t, want.attempts[0].t)


def test_analysis_error_becomes_its_code() -> None:
    t, mm = tof_track(5)
    assert _over_wire("reach", t=t, mm=mm, marks=[]) == {
        "ok": False,
        "error": "no_descent_detected",
    }


def test_unknown_op_and_bad_args_are_bad_request() -> None:
    assert run_op("tap", {})["error"] == "bad_request"
    assert run_op("tremor", [])["error"] == "bad_request"
    assert run_op("tremor", {"t": [1.0]})["error"] == "bad_request"
