"""Posture tremor gated by hand height: only in-band ToF runs count."""

import numpy as np
from numpy.typing import NDArray

from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.sampling import effective_fs
from tremorlab.analysis.tremor import (
    DURATION_TOL_SAMPLES,
    TremorResult,
    _result_from_spectrum,
    tremor_spectrum,
)

BAND_HALF_WIDTH_MM = 30.0
MIN_RUN_S = 4.0
MIN_VALID_S = 20.0
TOF_VALID_RANGE_MM = (20.0, 1300.0)
TOF_MATCH_MAX_S = 0.2


def band_from_start(start_mm: float, half_width: float = BAND_HALF_WIDTH_MM) -> tuple[float, float]:
    """(start - half_width, start + half_width) in mm."""
    return (start_mm - half_width, start_mm + half_width)


def in_band_mask(
    t_imu: NDArray[np.float64],
    t_tof: NDArray[np.float64],
    mm: NDArray[np.float64],
    band: tuple[float, float],
) -> NDArray[np.bool_]:
    """Per-IMU-sample in-band flag; invalid ToF dropped; IMU >0.2 s from valid ToF is out."""
    lo, hi = TOF_VALID_RANGE_MM
    valid = np.isfinite(t_tof) & np.isfinite(mm) & (mm >= lo) & (mm <= hi)
    if not valid.any() or t_imu.size == 0:
        return np.zeros(t_imu.shape, dtype=np.bool_)
    order = np.argsort(t_tof[valid], kind="stable")
    # Work relative to the first valid reading to keep precision with epoch-second timestamps.
    ref = float(t_tof[valid][order[0]])
    xp = t_tof[valid][order] - ref
    fp = mm[valid][order]
    x = t_imu - ref
    height = np.interp(x, xp, fp)
    j = np.searchsorted(xp, x)
    before = xp[np.clip(j - 1, 0, xp.size - 1)]
    after = xp[np.clip(j, 0, xp.size - 1)]
    nearest = np.minimum(np.abs(x - before), np.abs(after - x))
    in_band = (height >= band[0]) & (height <= band[1]) & (nearest <= TOF_MATCH_MAX_S)
    return np.asarray(in_band, dtype=np.bool_)


def _runs(mask: NDArray[np.bool_]) -> list[tuple[int, int]]:
    """[start, stop) index pairs of contiguous True runs."""
    edges = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    starts = np.flatnonzero(edges == 1)
    stops = np.flatnonzero(edges == -1)
    return [(int(a), int(b)) for a, b in zip(starts, stops, strict=True)]


def analyze_posture(
    t_imu: NDArray[np.float64],
    acc: NDArray[np.float64],
    t_tof: NDArray[np.float64],
    mm: NDArray[np.float64],
    band: tuple[float, float],
) -> TremorResult:
    """Weighted PSD over in-band runs ≥ MIN_RUN_S; insufficient_valid_data under MIN_VALID_S."""
    fs = effective_fs(t_imu)
    tol_s = DURATION_TOL_SAMPLES / fs
    mask = in_band_mask(t_imu, t_tof, mm, band)
    runs = [(a, b) for a, b in _runs(mask) if (b - a) / fs >= MIN_RUN_S - tol_s]
    valid_seconds = sum(b - a for a, b in runs) / fs
    if valid_seconds < MIN_VALID_S - tol_s:
        raise AnalysisError(
            "insufficient_valid_data", f"{valid_seconds:.1f} s of posture held in band"
        )
    spectra = [tremor_spectrum(t_imu[a:b], acc[a:b]) for a, b in runs]
    weights = np.array([b - a for a, b in runs], dtype=np.float64)
    # Runs can differ by a sample in Welch length, so put every PSD on the longest run's grid.
    grid = spectra[int(np.argmax(weights))][0]
    stacked = np.vstack([np.interp(grid, f, p) for f, p, _ in spectra])
    psd = np.asarray(weights @ stacked / weights.sum(), dtype=np.float64)
    return _result_from_spectrum(grid, psd, valid_seconds)
