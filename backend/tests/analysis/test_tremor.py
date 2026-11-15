import math

import numpy as np
import pytest

from tests.analysis.synth import AXIS_WEIGHTS, sine_imu, still_imu
from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.tremor import (
    BAND_HZ,
    MIN_SECONDS,
    RMS_MIN_MS2,
    SCORE_CEIL_MS2,
    SCORE_FLOOR_MS2,
    analyze_tremor,
    strength_to_score,
    tremor_spectrum,
)


@pytest.mark.parametrize("hz", [4.0, 5.0, 6.0, 8.0])
def test_peak_frequency_within_quarter_hz(hz: float) -> None:
    r = analyze_tremor(*sine_imu(hz, 0.3, 30))
    assert r.tremor_detected
    assert r.peak_hz is not None and abs(r.peak_hz - hz) <= 0.25


@pytest.mark.parametrize("hz", [4.1, 5.37, 6.6])
def test_off_bin_peak_is_refined(hz: float) -> None:
    r = analyze_tremor(*sine_imu(hz, 0.3, 30))
    assert r.peak_hz is not None and abs(r.peak_hz - hz) <= 0.1


def test_still_hand_reports_no_clear_tremor() -> None:
    r = analyze_tremor(*still_imu(30))
    assert not r.tremor_detected and r.peak_hz is None
    assert r.strength_ms2 < 0.02


@pytest.mark.parametrize("seed", range(5))
def test_still_hand_never_detected_across_seeds(seed: int) -> None:
    assert not analyze_tremor(*still_imu(30, seed=seed)).tremor_detected


def test_jittery_97hz_still_reads_5hz() -> None:
    r = analyze_tremor(*sine_imu(5.0, 0.3, 30, fs=97, jitter_s=0.001))
    assert r.tremor_detected
    assert r.peak_hz is not None and abs(r.peak_hz - 5.0) <= 0.25


def test_strength_rms_matches_amplitude() -> None:
    amp = 0.3
    r = analyze_tremor(*sine_imu(5.0, amp, 30))
    expected = amp * math.sqrt(sum(w * w for w in AXIS_WEIGHTS)) / math.sqrt(2)
    assert r.strength_ms2 == pytest.approx(expected, rel=0.10)


def test_gravity_and_slow_drift_do_not_leak_into_band() -> None:
    plain = analyze_tremor(*sine_imu(5.0, 0.3, 30))
    drifting = analyze_tremor(*sine_imu(5.0, 0.3, 30, drift_amp=0.5))
    assert drifting.strength_ms2 == pytest.approx(plain.strength_ms2, rel=0.02)


def test_weak_tremor_below_rms_floor_is_not_detected() -> None:
    r = analyze_tremor(*sine_imu(5.0, 0.1, 30, noise=0.001))
    assert r.strength_ms2 < RMS_MIN_MS2 and not r.tremor_detected and r.peak_hz is None


def test_score_mapping_endpoints() -> None:
    assert strength_to_score(SCORE_FLOOR_MS2) == 0
    assert strength_to_score(SCORE_CEIL_MS2) == 100
    assert strength_to_score(0.1) > strength_to_score(0.05)


def test_score_is_fifty_points_per_decade() -> None:
    assert strength_to_score(0.5) == pytest.approx(50.0)
    assert strength_to_score(0.14) == pytest.approx(22.4, abs=0.1)


def test_still_hand_level_scores_near_zero() -> None:
    assert strength_to_score(0.057) < 5


def test_score_clamps_out_of_range() -> None:
    assert strength_to_score(0.0) == 0
    assert strength_to_score(0.01) == 0
    assert strength_to_score(20.0) == 100


@pytest.mark.parametrize("seed", range(5))
def test_mild_tremor_just_above_gate_is_detected(seed: int) -> None:
    r = analyze_tremor(*sine_imu(5.0, 0.22, 30, seed=seed))
    assert r.tremor_detected and r.strength_ms2 >= RMS_MIN_MS2
    assert r.peak_hz is not None and abs(r.peak_hz - 5.0) <= 0.25


@pytest.mark.parametrize("seconds", [8.0, 4.5])
def test_mild_tremor_detected_in_live_window(seconds: float) -> None:
    r = analyze_tremor(*sine_imu(5.0, 0.22, seconds), trim=False)
    assert r.tremor_detected


def test_physiological_level_tremor_is_not_detected() -> None:
    r = analyze_tremor(*sine_imu(9.5, 0.12, 30))
    assert r.strength_ms2 < RMS_MIN_MS2 and not r.tremor_detected and r.peak_hz is None


def test_short_recording_raises_insufficient() -> None:
    with pytest.raises(AnalysisError) as e:
        analyze_tremor(*sine_imu(5, 0.3, 5))
    assert e.value.code == "insufficient_valid_data"


def test_empty_recording_raises_insufficient() -> None:
    with pytest.raises(AnalysisError) as e:
        analyze_tremor(np.zeros(0), np.zeros((0, 3)))
    assert e.value.code == "insufficient_valid_data"


def test_exactly_min_seconds_is_accepted() -> None:
    r = analyze_tremor(*sine_imu(5.0, 0.3, MIN_SECONDS), trim=False)
    assert r.valid_seconds == pytest.approx(MIN_SECONDS)


def test_untrimmed_short_window_for_live_spectrum() -> None:
    r = analyze_tremor(*sine_imu(5.0, 0.3, 6), trim=False)
    assert r.valid_seconds == pytest.approx(6.0, abs=0.05)
    assert r.peak_hz is not None and abs(r.peak_hz - 5.0) <= 0.25


def test_valid_seconds_excludes_trimmed_edges() -> None:
    r = analyze_tremor(*sine_imu(5.0, 0.3, 30))
    assert r.valid_seconds == pytest.approx(26.0, abs=0.05)


def test_spectrum_returned_for_display() -> None:
    r = analyze_tremor(*sine_imu(5.0, 0.3, 30))
    assert r.freqs.shape == r.psd.shape
    assert r.freqs[1] - r.freqs[0] == pytest.approx(0.25, abs=0.01)
    assert r.freqs[0] == 0 and r.freqs[-1] >= BAND_HZ[1]


def test_tremor_spectrum_reports_fs_and_resolution() -> None:
    freqs, psd, fs = tremor_spectrum(*sine_imu(5.0, 0.3, 20, fs=97, jitter_s=0.001))
    assert abs(fs - 97) < 0.5
    assert freqs.shape == psd.shape
    assert freqs[1] - freqs[0] == pytest.approx(0.25, abs=0.01)
