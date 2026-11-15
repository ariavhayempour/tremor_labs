import numpy as np
import pytest

from tests.analysis.synth import AXIS_WEIGHTS, T0, sine_imu, tof_track
from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.posture import (
    MIN_RUN_S,
    POSTURE_RMS_MIN_MS2,
    analyze_posture,
    apply_posture_gate,
    band_from_start,
    in_band_mask,
)
from tremorlab.analysis.tremor import RMS_MIN_MS2, TremorResult, analyze_tremor

BAND = (170.0, 230.0)


# Comfortably above the posture gate, so mechanics tests don't depend on sensitivity.
POSTURE_TEST_AMP = 0.5


def _set_tof(t: np.ndarray, mm: np.ndarray, start_s: float, end_s: float, value: float) -> None:
    mm[(t >= T0 + start_s) & (t < T0 + end_s)] = value


def test_band_from_start() -> None:
    assert band_from_start(200.0) == (170.0, 230.0)
    assert band_from_start(200.0, half_width=10.0) == (190.0, 210.0)


def test_all_in_band_gives_same_peak_as_rest() -> None:
    t, acc = sine_imu(5.0, POSTURE_TEST_AMP, 30)
    rest = analyze_tremor(t, acc, trim=False)
    r = analyze_posture(t, acc, *tof_track(30), BAND)
    assert r.tremor_detected
    assert r.peak_hz is not None and rest.peak_hz is not None
    assert abs(r.peak_hz - rest.peak_hz) <= 0.05
    assert r.strength_ms2 == pytest.approx(rest.strength_ms2, rel=0.05)
    assert r.valid_seconds == pytest.approx(30.0, abs=0.5)
    assert r.freqs.shape == r.psd.shape


def test_out_of_band_segment_excluded() -> None:
    t, acc = sine_imu(5.0, POSTURE_TEST_AMP, 30)
    middle = (t >= T0 + 11.0) & (t < T0 + 19.0)
    # A stronger 9 Hz movement while out of band must not reach the result.
    acc[middle] += np.outer(2.0 * np.sin(2 * np.pi * 9.0 * (t[middle] - T0)), AXIS_WEIGHTS)
    t_tof, mm = tof_track(30)
    _set_tof(t_tof, mm, 11.0, 19.0, 300.0)
    r = analyze_posture(t, acc, t_tof, mm, BAND)
    assert r.valid_seconds == pytest.approx(22.0, abs=1.0)
    assert r.peak_hz is not None and abs(r.peak_hz - 5.0) <= 0.25
    in_band_rms = POSTURE_TEST_AMP * float(np.linalg.norm(AXIS_WEIGHTS)) / np.sqrt(2)
    assert r.strength_ms2 == pytest.approx(in_band_rms, rel=0.1)  # the 9 Hz burst would add ~1.4


def test_less_than_20s_valid_raises() -> None:
    t, acc = sine_imu(5.0, POSTURE_TEST_AMP, 30)
    t_tof, mm = tof_track(30)
    _set_tof(t_tof, mm, 9.0, 21.0, 300.0)
    with pytest.raises(AnalysisError) as e:
        analyze_posture(t, acc, t_tof, mm, BAND)
    assert e.value.code == "insufficient_valid_data"


def test_short_recording_all_in_band_raises() -> None:
    t, acc = sine_imu(5.0, POSTURE_TEST_AMP, 15)
    with pytest.raises(AnalysisError) as e:
        analyze_posture(t, acc, *tof_track(15), BAND)
    assert e.value.code == "insufficient_valid_data"


def test_runs_shorter_than_min_run_are_dropped() -> None:
    t, acc = sine_imu(5.0, POSTURE_TEST_AMP, 60)
    t_tof, mm = tof_track(60)
    step = MIN_RUN_S - 1.0
    for k in range(int(60 / step)):
        if k % 2:
            _set_tof(t_tof, mm, k * step, (k + 1) * step, 300.0)
    with pytest.raises(AnalysisError) as e:
        analyze_posture(t, acc, t_tof, mm, BAND)
    assert e.value.code == "insufficient_valid_data"


def test_nan_and_out_of_range_tof_count_as_out_of_band() -> None:
    t, acc = sine_imu(5.0, POSTURE_TEST_AMP, 40)
    t_tof, mm = tof_track(40)
    full = analyze_posture(t, acc, t_tof, mm, BAND).valid_seconds
    _set_tof(t_tof, mm, 8.0, 11.0, np.nan)
    _set_tof(t_tof, mm, 18.0, 21.0, 0.0)
    _set_tof(t_tof, mm, 28.0, 31.0, 1500.0)
    r = analyze_posture(t, acc, t_tof, mm, BAND)
    assert r.valid_seconds < full - 7.0
    assert r.peak_hz is not None and abs(r.peak_hz - 5.0) <= 0.25


def test_mostly_invalid_tof_raises_only_insufficient() -> None:
    t, acc = sine_imu(5.0, POSTURE_TEST_AMP, 30)
    t_tof, mm = tof_track(30)
    _set_tof(t_tof, mm, 5.0, 12.0, np.nan)
    _set_tof(t_tof, mm, 12.0, 18.0, 0.0)
    _set_tof(t_tof, mm, 18.0, 25.0, 1500.0)
    with pytest.raises(AnalysisError) as e:
        analyze_posture(t, acc, t_tof, mm, BAND)
    assert e.value.code == "insufficient_valid_data"


def test_all_nan_tof_raises_insufficient() -> None:
    t, acc = sine_imu(5.0, POSTURE_TEST_AMP, 30)
    t_tof, _ = tof_track(30)
    with pytest.raises(AnalysisError) as e:
        analyze_posture(t, acc, t_tof, np.full(t_tof.size, np.nan), BAND)
    assert e.value.code == "insufficient_valid_data"


def test_in_band_mask_drops_imu_far_from_valid_tof() -> None:
    t_imu = T0 + np.arange(1000) / 100.0
    t_tof = T0 + np.arange(400) / 40.0
    mm = np.full(t_tof.size, 200.0)
    _set_tof(t_tof, mm, 4.0, 6.0, np.nan)
    mask = in_band_mask(t_imu, t_tof, mm, BAND)
    rel = t_imu - T0
    assert mask[(rel < 3.9)].all()
    assert not mask[(rel > 4.2) & (rel < 5.75)].any()
    assert mask[(rel > 6.2)].all()


def test_in_band_mask_band_edges_and_interpolation() -> None:
    t_tof = T0 + np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    mm = np.array([200.0, 240.0, 200.0, 169.0, 230.0])
    t_imu = T0 + np.array([0.05, 0.1, 0.15, 0.3, 0.4])
    mask = in_band_mask(t_imu, t_tof, mm, BAND)
    assert mask.tolist() == [True, False, True, False, True]


def test_in_band_mask_outside_tof_span() -> None:
    t_tof = T0 + 5.0 + np.arange(40) / 40.0
    mm = np.full(t_tof.size, 200.0)
    t_imu = T0 + np.array([4.0, 4.9, 5.5, 6.1, 7.0])
    mask = in_band_mask(t_imu, t_tof, mm, BAND)
    assert mask.tolist() == [False, True, True, True, False]


def test_in_band_mask_empty_tof() -> None:
    t_imu = T0 + np.arange(10) / 100.0
    mask = in_band_mask(t_imu, np.zeros(0), np.zeros(0), BAND)
    assert mask.dtype == np.bool_ and mask.shape == t_imu.shape and not mask.any()


def _result(strength: float, detected: bool = True) -> TremorResult:
    freqs = np.arange(0.0, 15.25, 0.25)
    return TremorResult(
        peak_hz=5.0 if detected else None,
        strength_ms2=strength,
        strength_score=40.0,
        tremor_detected=detected,
        freqs=freqs,
        psd=np.ones_like(freqs),
        valid_seconds=8.0,
    )


def test_posture_gate_is_stricter_than_rest() -> None:
    assert POSTURE_RMS_MIN_MS2 > RMS_MIN_MS2


def test_apply_posture_gate_clears_detection_below_gate() -> None:
    r = apply_posture_gate(_result(POSTURE_RMS_MIN_MS2 * 0.9))
    assert not r.tremor_detected and r.peak_hz is None
    assert r.strength_ms2 == pytest.approx(POSTURE_RMS_MIN_MS2 * 0.9)  # strength still reported


def test_apply_posture_gate_keeps_detection_above_gate() -> None:
    r = apply_posture_gate(_result(POSTURE_RMS_MIN_MS2 * 1.1))
    assert r.tremor_detected and r.peak_hz == 5.0


def test_apply_posture_gate_never_creates_a_detection() -> None:
    assert not apply_posture_gate(_result(1.0, detected=False)).tremor_detected


def test_posture_sensitivity_matches_gate() -> None:
    # sine_imu band RMS = amp·norm(AXIS_WEIGHTS)/sqrt(2); test 10% either side of the gate.
    gain = float(np.sqrt(np.sum(np.square(AXIS_WEIGHTS))) / np.sqrt(2))
    t, acc = sine_imu(5.0, POSTURE_RMS_MIN_MS2 * 1.1 / gain, 30)
    t_tof, mm = tof_track(30)
    assert analyze_posture(t, acc, t_tof, mm, BAND).tremor_detected
    t, acc = sine_imu(5.0, POSTURE_RMS_MIN_MS2 * 0.9 / gain, 30)
    assert not analyze_posture(t, acc, t_tof, mm, BAND).tremor_detected
