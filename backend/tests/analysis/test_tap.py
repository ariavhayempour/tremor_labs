import itertools

import numpy as np
import pytest

from tests.analysis.synth import tap_frames
from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.tap import TapFrame, analyze_taps, tap_signal


def test_rate_recovered_4hz() -> None:
    assert abs(analyze_taps(tap_frames()).taps_per_sec - 4) < 0.2


def test_decrement_30_percent() -> None:
    assert analyze_taps(tap_frames()).decrement == pytest.approx(-0.3, abs=0.08)


def test_regular_rhythm_low_cv() -> None:
    assert analyze_taps(tap_frames()).rhythm_cv < 0.1


def test_missing_frames_are_skipped() -> None:
    frames = tap_frames(drop_every=7, fps_jitter=0.2)
    r = analyze_taps(frames)
    assert abs(r.taps_per_sec - 4) < 0.3
    assert r.t.size == sum(f.lm is not None for f in frames)


def test_no_taps_raises() -> None:
    with pytest.raises(AnalysisError) as e:
        analyze_taps(tap_frames(amp_start=0.05, amp_end=0.05))
    assert e.value.code == "no_taps_detected"


def test_no_hand_at_all_raises_no_taps() -> None:
    with pytest.raises(AnalysisError) as e:
        analyze_taps([TapFrame(t=i / 30, lm=None) for i in range(300)])
    assert e.value.code == "no_taps_detected"


def test_empty_frames_raise_no_taps() -> None:
    with pytest.raises(AnalysisError) as e:
        analyze_taps([])
    assert e.value.code == "no_taps_detected"


def test_signal_is_tip_gap_over_hand_size() -> None:
    lm = ((0.5, 0.8), (0.4, 0.4), (0.4, 0.55), (0.5, 0.5))
    t, s = tap_signal([TapFrame(1.0, lm), TapFrame(1.1, None), TapFrame(1.2, lm)])
    assert t.tolist() == [1.0, 1.2]
    assert s == pytest.approx([0.5, 0.5])


def test_degenerate_hand_size_frame_is_dropped() -> None:
    bad = ((0.5, 0.5), (0.4, 0.4), (0.4, 0.55), (0.5, 0.5))
    t, _ = tap_signal([TapFrame(1.0, bad)])
    assert t.size == 0


def test_amplitude_is_peak_minus_preceding_trough() -> None:
    r = analyze_taps(tap_frames(amp_start=0.8, amp_end=0.8))
    assert r.amplitude == pytest.approx(0.8, abs=0.06)
    assert r.decrement == pytest.approx(0.0, abs=0.05)


def test_irregular_rhythm_raises_cv() -> None:
    frames = tap_frames()
    rng = np.random.default_rng(1)
    warped, clock = [], frames[0].t
    for prev, f in itertools.pairwise(frames):
        warped.append(TapFrame(clock, prev.lm))
        clock += (f.t - prev.t) * float(rng.choice([0.6, 1.6]))
    regular = analyze_taps(frames).rhythm_cv
    assert analyze_taps(warped).rhythm_cv > regular + 0.1


def test_result_arrays_line_up() -> None:
    r = analyze_taps(tap_frames())
    assert r.t.shape == r.signal.shape
    assert r.peak_idx.dtype == np.int64 and r.peak_idx.size >= 35
    assert np.all(np.diff(r.t) > 0)


def test_unsorted_frames_are_ordered_by_time() -> None:
    frames = tap_frames()
    r = analyze_taps(list(reversed(frames)))
    assert abs(r.taps_per_sec - 4) < 0.2
