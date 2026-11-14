import numpy as np
import pytest

from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.sampling import (
    effective_fs,
    max_gap,
    needs_resample,
    resample_uniform,
    trim_edges,
)

T0 = 1_700_000_000.0


def _uniform_t(seconds: float, fs: float) -> np.ndarray:
    return T0 + np.arange(round(seconds * fs)) / fs


def _jittered_t(seconds: float, fs: float, jitter_s: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = _uniform_t(seconds, fs)
    return t + rng.uniform(-jitter_s, jitter_s, t.shape)


def test_effective_fs_at_97hz_with_jitter() -> None:
    fs = effective_fs(_jittered_t(30, 97.0, 0.001))
    assert abs(fs - 97) < 0.5


def test_effective_fs_rejects_fewer_than_two_samples() -> None:
    with pytest.raises(AnalysisError) as e:
        effective_fs(np.array([T0]))
    assert e.value.code == "insufficient_valid_data"


def test_trim_edges_drops_2s_each_side() -> None:
    t = _uniform_t(30, 100.0)
    x = np.zeros((t.size, 3))
    tt, xt = trim_edges(t, x)
    assert abs(tt.size - 2600) <= 2
    assert xt.shape == (tt.size, 3)
    assert tt[0] >= t[0] + 2.0 and tt[-1] <= t[-1] - 2.0


def test_trim_edges_of_short_recording_is_empty() -> None:
    t = _uniform_t(3, 100.0)
    tt, xt = trim_edges(t, np.zeros(t.size))
    assert tt.size == 0 and xt.size == 0


def test_needs_resample_false_for_uniform_true_for_jittery() -> None:
    assert not needs_resample(_uniform_t(10, 100.0))
    assert needs_resample(_jittered_t(10, 97.0, 0.001))


def test_resample_uniform_preserves_sine_frequency() -> None:
    hz = 5.0
    t = _jittered_t(20, 97.0, 0.001)
    x = np.sin(2 * np.pi * hz * (t - T0))
    tu, xu = resample_uniform(t, x, 97.0)
    dt = np.diff(tu)
    assert tu[0] == t[0] and tu[-1] <= t[-1]
    assert np.allclose(dt, 1 / 97.0, atol=1e-6)
    spec = np.abs(np.fft.rfft(xu))
    freqs = np.fft.rfftfreq(xu.size, 1 / 97.0)
    assert abs(freqs[np.argmax(spec)] - hz) <= 0.1


def test_resample_uniform_handles_multiaxis() -> None:
    t = _jittered_t(5, 100.0, 0.001)
    x = np.column_stack([t - T0, 2 * (t - T0), np.ones_like(t)])
    tu, xu = resample_uniform(t, x, 100.0)
    assert xu.shape == (tu.size, 3)
    assert np.allclose(xu[:, 1], 2 * (tu - T0))


def test_max_gap_detects_1_5s_hole() -> None:
    t = _uniform_t(10, 100.0)
    t = np.concatenate([t[t < T0 + 4.0], t[t >= T0 + 5.5]])
    assert abs(max_gap(t) - 1.5) < 0.02


def test_max_gap_of_single_sample_is_zero() -> None:
    assert max_gap(np.array([T0])) == 0.0
