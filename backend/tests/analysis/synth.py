"""Synthetic IMU and ToF signals for analysis tests (SI units, epoch-second timestamps)."""

import numpy as np
from numpy.typing import NDArray

GRAVITY_MS2 = 9.80665
AXIS_WEIGHTS = (0.6, 0.6, 0.5)
T0 = 1_700_000_000.0

Arr = NDArray[np.float64]


def _times(seconds: float, fs: float, jitter_s: float, rng: np.random.Generator) -> Arr:
    t = np.arange(round(seconds * fs), dtype=np.float64) / fs
    if jitter_s > 0:
        t = t + rng.uniform(-jitter_s, jitter_s, t.shape)
    return t


def sine_imu(
    hz: float,
    amp: float,
    seconds: float,
    fs: float = 100,
    noise: float = 0.02,
    jitter_s: float = 0.0,
    seed: int = 0,
    drift_amp: float = 0.0,
    drift_hz: float = 0.05,
) -> tuple[Arr, Arr]:
    """(t s, acc (N, 3) m/s²): amp·weights·sin at hz, gravity on z, Gaussian noise per axis."""
    rng = np.random.default_rng(seed)
    rel = _times(seconds, fs, jitter_s, rng)
    wave = amp * np.sin(2 * np.pi * hz * rel) + drift_amp * np.sin(2 * np.pi * drift_hz * rel)
    acc = np.outer(wave, AXIS_WEIGHTS) + rng.normal(0.0, noise, (rel.size, 3))
    acc[:, 2] += GRAVITY_MS2
    return T0 + rel, acc


def still_imu(seconds: float, noise: float = 0.02, seed: int = 0) -> tuple[Arr, Arr]:
    """A still hand: gravity on z plus noise, 100 Hz."""
    return sine_imu(5.0, 0.0, seconds, noise=noise, seed=seed)


def tof_track(
    seconds: float, mm: float = 200.0, fs: float = 40, noise: float = 1.0, seed: int = 0
) -> tuple[Arr, Arr]:
    """(t s, distance mm) held at mm with Gaussian noise, same epoch start as the IMU."""
    rng = np.random.default_rng(seed + 1)
    rel = _times(seconds, fs, 0.0, rng)
    return T0 + rel, mm + rng.normal(0.0, noise, rel.size)
