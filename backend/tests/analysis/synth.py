"""Synthetic IMU and ToF signals for analysis tests (SI units, epoch-second timestamps)."""

import numpy as np
from numpy.typing import NDArray

from tremorlab.analysis.tap import EDGE_WINDOW_S, TapFrame

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


DESCENT_HOLD_S = 1.0
WOBBLE_HZ = 8.0
WOBBLE_ZONE_MM = 50.0


def _min_jerk(p: Arr) -> Arr:
    return 10 * p**3 - 15 * p**4 + 6 * p**5


def descent_tof(
    start: float = 300,
    end: float = 30,
    seconds: float = 2.5,
    fs: float = 40,
    noise: float = 1.0,
    wobble_mm: float = 0.0,
    seed: int = 0,
) -> tuple[Arr, Arr]:
    """(t s, mm): 1 s at start, min-jerk descent, 1 s at end; 8 Hz wobble in the last 50 mm."""
    rng = np.random.default_rng(seed + 2)
    rel = _times(seconds + 2 * DESCENT_HOLD_S, fs, 0.0, rng)
    progress = np.clip((rel - DESCENT_HOLD_S) / seconds, 0.0, 1.0)
    path = start - (start - end) * _min_jerk(progress)
    moving = (progress > 0) & (progress < 1)
    zone = moving & (path < end + WOBBLE_ZONE_MM)
    path = path + np.where(zone, wobble_mm * np.sin(2 * np.pi * WOBBLE_HZ * rel), 0.0)
    return T0 + rel, path + rng.normal(0.0, noise, rel.size)


HAND_SCALE = 0.3
CLOSED_GAP = 0.05
LANDMARK_NOISE = 0.002


def tap_frames(
    rate_hz: float = 4,
    seconds: float = 10,
    fps: float = 30,
    amp_start: float = 1.0,
    amp_end: float = 0.7,
    drop_every: int = 0,
    fps_jitter: float = 0.0,
    seed: int = 0,
) -> list[TapFrame]:
    """Thumb-index taps at rate_hz; amplitude (signal units) holds amp_start for the first
    EDGE_WINDOW_S, ramps linearly, then holds amp_end for the last EDGE_WINDOW_S.
    fps_jitter is the ± fraction of each frame interval; every drop_every-th frame has no hand."""
    rng = np.random.default_rng(seed + 3)
    n = round(seconds * fps)
    dt = (1.0 / fps) * (1.0 + rng.uniform(-fps_jitter, fps_jitter, n))
    rel = np.concatenate(([0.0], np.cumsum(dt[:-1])))
    ramp = np.clip((rel - EDGE_WINDOW_S) / max(seconds - 2 * EDGE_WINDOW_S, 1e-9), 0.0, 1.0)
    amp = amp_start + (amp_end - amp_start) * ramp
    gap = CLOSED_GAP + amp * (1 - np.cos(2 * np.pi * rate_hz * rel)) / 2
    frames = []
    for i, (ti, g) in enumerate(zip(rel, gap, strict=True)):
        if drop_every and i % drop_every == drop_every - 1:
            frames.append(TapFrame(t=1_000.0 + float(ti), lm=None))
            continue
        jit = rng.normal(0.0, LANDMARK_NOISE, 8)
        wrist = (0.5 + jit[0], 0.8 + jit[1])
        mcp = (0.5 + jit[2], 0.8 - HAND_SCALE + jit[3])
        thumb = (0.45 + jit[4], 0.4 + jit[5])
        index = (0.45 + HAND_SCALE * float(g) + jit[6], 0.4 + jit[7])
        frames.append(TapFrame(t=1_000.0 + float(ti), lm=(wrist, thumb, index, mcp)))
    return frames
