"""Rest/posture tremor: high-pass, Welch PSD, 3-12 Hz peak, band RMS, detection and score."""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.signal import butter, sosfiltfilt, welch

from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.sampling import effective_fs, needs_resample, resample_uniform, trim_edges

HP_CUTOFF_HZ = 2.0
BAND_HZ = (3.0, 12.0)
WELCH_WINDOW_S = 4.0
PEAK_TO_MEDIAN_MIN = 6.0
RMS_MIN_MS2 = 0.14
SCORE_FLOOR_MS2 = 0.05
SCORE_CEIL_MS2 = 5.0
MIN_SECONDS = 4.0

HP_ORDER = 4
MIN_SPECTRUM_S = 1.0
PEAK_MAX_SHIFT_BINS = 0.5
DURATION_TOL_SAMPLES = 0.5


@dataclass(frozen=True)
class TremorResult:
    """peak_hz Hz (None if no tremor detected); strength_ms2 m/s² band RMS; score 0-100;
    freqs Hz; psd (m/s²)²/Hz summed over axes; valid_seconds s analyzed."""

    peak_hz: float | None
    strength_ms2: float
    strength_score: float
    tremor_detected: bool
    freqs: NDArray[np.float64]
    psd: NDArray[np.float64]
    valid_seconds: float


def strength_to_score(rms_ms2: float) -> float:
    """rms m/s² → 0-100: log10 scale from SCORE_FLOOR_MS2 (0) to SCORE_CEIL_MS2 (100), clamped."""
    if not rms_ms2 > SCORE_FLOOR_MS2:
        return 0.0
    score = (
        100.0 * math.log10(rms_ms2 / SCORE_FLOOR_MS2) / math.log10(SCORE_CEIL_MS2 / SCORE_FLOOR_MS2)
    )
    return min(max(score, 0.0), 100.0)


def _finite_rows(
    t: NDArray[np.float64], acc: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Drop samples whose timestamp or any axis is NaN/inf."""
    keep = np.isfinite(t) & np.all(np.isfinite(acc), axis=1)
    return t[keep], acc[keep]


def tremor_spectrum(
    t: NDArray[np.float64], acc: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
    """t (N,) s, acc (N, 3) m/s² → (freqs Hz, summed PSD (m/s²)²/Hz, fs Hz)."""
    t, acc = _finite_rows(t, acc)
    fs = effective_fs(t)
    if t.size / fs < MIN_SPECTRUM_S or fs <= 2 * BAND_HZ[1]:
        raise AnalysisError("insufficient_valid_data", "too little data for a spectrum")
    if needs_resample(t):
        t, acc = resample_uniform(t, acc, fs)
    sos = butter(HP_ORDER, HP_CUTOFF_HZ, btype="highpass", fs=fs, output="sos")
    filtered = sosfiltfilt(sos, acc, axis=0)
    nperseg = min(round(WELCH_WINDOW_S * fs), t.size)
    freqs, pxx = welch(filtered, fs=fs, nperseg=nperseg, noverlap=nperseg // 2, axis=0)
    psd = np.asarray(pxx, dtype=np.float64).sum(axis=1)
    return np.asarray(freqs, dtype=np.float64), psd, fs


def _refine_peak(freqs: NDArray[np.float64], psd: NDArray[np.float64], k: int) -> float:
    """Parabolic interpolation of log PSD around bin k, in Hz."""
    if k <= 0 or k >= psd.size - 1 or np.any(psd[k - 1 : k + 2] <= 0):
        return float(freqs[k])
    a, b, c = np.log(psd[k - 1 : k + 2])
    denom = a - 2 * b + c
    if denom >= 0:
        return float(freqs[k])
    shift = float(np.clip(0.5 * (a - c) / denom, -PEAK_MAX_SHIFT_BINS, PEAK_MAX_SHIFT_BINS))
    return float(freqs[k] + shift * (freqs[1] - freqs[0]))


def _result_from_spectrum(
    freqs: NDArray[np.float64], psd: NDArray[np.float64], valid_seconds: float
) -> TremorResult:
    """Peak, band RMS (integrated PSD over BAND_HZ), detection and score from a summed PSD."""
    idx = np.flatnonzero((freqs >= BAND_HZ[0]) & (freqs <= BAND_HZ[1]))
    df = float(freqs[1] - freqs[0])
    rms = math.sqrt(float(np.sum(psd[idx])) * df)
    k = int(idx[np.argmax(psd[idx])])
    clear_peak = float(psd[k]) >= PEAK_TO_MEDIAN_MIN * float(np.median(psd[idx]))
    detected = clear_peak and rms >= RMS_MIN_MS2
    return TremorResult(
        peak_hz=_refine_peak(freqs, psd, k) if detected else None,
        strength_ms2=rms,
        strength_score=strength_to_score(rms),
        tremor_detected=detected,
        freqs=freqs,
        psd=psd,
        valid_seconds=valid_seconds,
    )


def analyze_tremor(
    t: NDArray[np.float64], acc: NDArray[np.float64], *, trim: bool = True
) -> TremorResult:
    """t (N,) s, acc (N, 3) m/s²; insufficient_valid_data under MIN_SECONDS of data."""
    t, acc = _finite_rows(t, acc)
    if trim:
        t, acc = trim_edges(t, acc)
    fs = effective_fs(t)
    valid_seconds = t.size / fs
    if valid_seconds < MIN_SECONDS - DURATION_TOL_SAMPLES / fs:
        raise AnalysisError("insufficient_valid_data", f"{valid_seconds:.1f} s analyzable")
    freqs, psd, _ = tremor_spectrum(t, acc)
    return _result_from_spectrum(freqs, psd, valid_seconds)
