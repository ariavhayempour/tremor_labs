from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from tremorlab.analysis.tremor import TremorResult, analyze_tremor

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "hardware"
STILL = FIXTURES / "still_hand.npz"
METRONOME = FIXTURES / "metronome_5hz.npz"
LIVE_STEP_S = 0.5
METRONOME_HZ = 5.0

Arr = NDArray[np.float64]

needs_still = pytest.mark.skipif(not STILL.exists(), reason="still-hand recording missing")
needs_metronome = pytest.mark.skipif(not METRONOME.exists(), reason="metronome recording missing")


def _load(path: Path) -> tuple[Arr, Arr]:
    with np.load(path) as d:
        return np.asarray(d["t"], dtype=np.float64), np.asarray(d["acc"], dtype=np.float64)


def _live_windows(t: Arr, acc: Arr, seconds: float) -> list[TremorResult]:
    """Sliding untrimmed windows, as the live spectrum computes them."""
    out = []
    start = float(t[0])
    while start + seconds <= float(t[-1]) + 1e-9:
        m = (t >= start) & (t < start + seconds)
        out.append(analyze_tremor(t[m], acc[m], trim=False))
        start += LIVE_STEP_S
    return out


def _near_5hz(r: TremorResult, tol: float) -> bool:
    return r.tremor_detected and r.peak_hz is not None and abs(r.peak_hz - METRONOME_HZ) <= tol


@needs_still
def test_real_still_hand_not_detected() -> None:
    r = analyze_tremor(*_load(STILL))
    assert not r.tremor_detected and r.peak_hz is None


@needs_still
def test_real_still_hand_scores_near_zero() -> None:
    assert analyze_tremor(*_load(STILL)).strength_score < 10


@needs_still
@pytest.mark.parametrize("seconds", [8.0, 4.5])
def test_real_still_hand_live_windows_not_detected(seconds: float) -> None:
    results = _live_windows(*_load(STILL), seconds)
    assert len(results) > 40
    assert sum(r.tremor_detected for r in results) == 0


@needs_metronome
def test_real_metronome_reads_5hz() -> None:
    assert _near_5hz(analyze_tremor(*_load(METRONOME)), 0.25)


@needs_metronome
def test_real_metronome_live_windows_detected() -> None:
    t, acc = _load(METRONOME)
    long = _live_windows(t, acc, 8.0)
    assert long and all(_near_5hz(r, 0.5) for r in long)
    short = _live_windows(t, acc, 4.5)
    assert short and sum(_near_5hz(r, 0.5) for r in short) >= 0.9 * len(short)
