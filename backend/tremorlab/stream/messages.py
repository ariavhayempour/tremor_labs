"""JSON-ready WebSocket message builders; shapes are documented in docs/contracts.md."""

from typing import Any

import numpy as np
from numpy.typing import NDArray

from tremorlab.sources.base import ImuBatch, SourceHealth, TofBatch

SPECTRUM_MAX_HZ = 15.0
SIG_FIGS = 4
UNKNOWN_FS_HZ = 1.0  # any positive rate is exact for a one-sample batch

Message = dict[str, Any]


TOF_OFFSET_DECIMALS = 6  # microsecond resolution keeps the JSON small


def batch_fs(t: NDArray[np.float64], fallback: float | None = None) -> float:
    """Effective rate in Hz of one batch, (N-1)/span from its timestamps (s)."""
    if len(t) >= 2:
        span = float(t[-1] - t[0])
        if span > 0:
            return (len(t) - 1) / span
    return fallback if fallback is not None else UNKNOWN_FS_HZ


def round_sig(values: NDArray[np.float64], figs: int = SIG_FIGS) -> list[float]:
    """Round to `figs` significant figures as plain floats."""
    return [float(f"{v:.{figs}g}") for v in values.tolist()]


def imu_msg(b: ImuBatch, *, fallback_fs: float | None = None) -> Message:
    """Rows are [ax, ay, az] m/s² then [gx, gy, gz] deg/s; sample i is at t0 + i/fs."""
    return {
        "type": "imu",
        "t0": float(b.t[0]),
        "fs": batch_fs(b.t, fallback_fs),
        "samples": np.hstack([b.acc, b.gyro]).tolist(),
    }


def tof_msg(b: TofBatch, *, fallback_fs: float | None = None) -> Message:
    """Distance in mm with non-finite readings dropped; t holds per-sample offsets from t0 in s."""
    valid = np.isfinite(b.mm)
    t, mm = b.t[valid], b.mm[valid]
    t0 = float(t[0]) if len(t) else float(b.t[0]) if len(b.t) else 0.0
    return {
        "type": "tof",
        "t0": t0,
        "fs": batch_fs(t, fallback_fs),
        "t": np.round(t - t0, TOF_OFFSET_DECIMALS).tolist(),
        "samples_mm": mm.tolist(),
    }


def spectrum_payload(
    freqs: NDArray[np.float64], psd: NDArray[np.float64]
) -> dict[str, list[float]]:
    """{"freqs" Hz, "psd" (m/s²)²/Hz} up to SPECTRUM_MAX_HZ, 4 significant figures."""
    keep = (freqs <= SPECTRUM_MAX_HZ) & np.isfinite(psd)
    return {"freqs": round_sig(freqs[keep]), "psd": round_sig(psd[keep])}


def spectrum_msg(
    freqs: NDArray[np.float64], psd: NDArray[np.float64], peak_hz: float | None
) -> Message:
    """Live spectrum; peak_hz Hz, None when no clear tremor."""
    return {
        "type": "spectrum",
        **spectrum_payload(freqs, psd),
        "peak_hz": None if peak_hz is None else float(peak_hz),
    }


def position_msg(
    tof_mm: float | None, in_band: bool, band: tuple[float, float], valid_seconds: float
) -> Message:
    """tof_mm mm (None when the latest reading is invalid); band mm; valid_seconds s."""
    return {
        "type": "position",
        "tof_mm": None if tof_mm is None else float(tof_mm),
        "in_band": bool(in_band),
        "band": [float(band[0]), float(band[1])],
        "valid_seconds": float(valid_seconds),
    }


def status_msg(recording: bool, test_id: int | None, test_type: str | None) -> Message:
    """seconds_left is always None: the frontend owns test timing."""
    return {
        "type": "status",
        "recording": recording,
        "test_id": test_id,
        "test_type": test_type,
        "seconds_left": None,
    }


def source_msg(health: SourceHealth, sensor_source: str) -> Message:
    return {
        "type": "source",
        "sensor_source": sensor_source,
        "connected": health.connected,
        "sensors": dict(health.sensors_detected),
        "imu_hz": health.imu_hz,
        "tof_hz": health.tof_hz,
    }
