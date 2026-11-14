import numpy as np
import pytest

from tests.analysis.synth import T0, descent_tof, tof_track
from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.reach import (
    END_MM,
    START_DROP_MM,
    _sg_window,
    analyze_reach,
    detect_descent,
)


def test_detects_single_descent_bounds() -> None:
    t, mm = descent_tof()
    bounds = detect_descent(t, mm)
    assert bounds is not None
    s, e = bounds
    assert mm[s] < np.max(mm[: s + 1]) - START_DROP_MM <= mm[s - 1]
    assert 1.3 < t[s] - T0 < 1.8
    assert mm[e] < END_MM and 2.7 < t[e] - T0 < 3.5


def test_smooth_descent_wobble_ratio_near_one() -> None:
    r = analyze_reach(*descent_tof(), [])
    assert len(r.attempts) == 1
    assert 0.6 <= r.wobble_ratio <= 1.6
    assert 0.5 < r.smoothness_mm < 1.5


def test_end_wobble_raises_ratio_above_1_5() -> None:
    smooth = analyze_reach(*descent_tof(), [])
    wobbly = analyze_reach(*descent_tof(wobble_mm=6.0), [])
    assert wobbly.wobble_ratio > 1.5
    assert wobbly.smoothness_mm > smooth.smoothness_mm


def test_three_marked_attempts_are_averaged() -> None:
    parts = [descent_tof(wobble_mm=w, seed=i) for i, w in enumerate([0.0, 3.0, 6.0])]
    span = parts[0][0][-1] - parts[0][0][0] + 0.025
    t = np.concatenate([p[0] + i * span for i, p in enumerate(parts)])
    mm = np.concatenate([p[1] for p in parts])
    marks = [T0 + span, T0 + 2 * span]
    r = analyze_reach(t, mm, marks)
    assert len(r.attempts) == 3
    wob = [a.wobble_ratio for a in r.attempts]
    assert wob[0] < wob[1] < wob[2]
    assert r.wobble_ratio == pytest.approx(float(np.mean(wob)))
    assert r.smoothness_mm == pytest.approx(float(np.mean([a.smoothness_mm for a in r.attempts])))


def test_flat_signal_raises_no_descent() -> None:
    with pytest.raises(AnalysisError) as e:
        analyze_reach(*tof_track(5.0), [])
    assert e.value.code == "no_descent_detected"


def test_reach_ignores_nan_samples() -> None:
    t, mm = descent_tof()
    clean = analyze_reach(t, mm, [])
    bad = mm.copy()
    bad[::9] = np.nan
    bad[4::13] = 0.0
    bad[7::17] = 1500.0
    r = analyze_reach(t, bad, [])
    a = r.attempts[0]
    assert np.all(np.isfinite(a.mm)) and np.all((a.mm > 0) & (a.mm <= 1300))
    assert a.t.shape == a.mm.shape == a.smoothed.shape == a.residual.shape
    assert r.smoothness_mm == pytest.approx(clean.smoothness_mm, rel=0.3)
    assert 0.6 <= r.wobble_ratio <= 1.6


def test_detect_descent_indices_skip_invalid_samples() -> None:
    t, mm = descent_tof()
    bad = mm.copy()
    bad[:10] = np.nan
    full, skipped = detect_descent(t, mm), detect_descent(t, bad)
    assert full is not None and skipped is not None
    assert t[10:][skipped[0]] == t[full[0]]


def test_board_rate_with_stale_repeats_and_gaps() -> None:
    t, mm = descent_tof(fs=50)
    clean = analyze_reach(t, mm, [])
    q = np.round(mm)
    rng = np.random.default_rng(5)
    stale = np.flatnonzero(rng.random(q.size) < 0.2)
    stale = stale[stale > 0]
    q[stale] = q[stale - 1]
    keep = rng.random(q.size) > 0.05
    r = analyze_reach(t[keep], q[keep], [])
    assert r.smoothness_mm == pytest.approx(clean.smoothness_mm, rel=0.35)
    assert 0.6 <= r.wobble_ratio <= 1.6


def test_stall_ends_descent_above_end_height() -> None:
    t, mm = descent_tof(end=150)
    bounds = detect_descent(t, mm)
    assert bounds is not None
    _, e = bounds
    assert mm[e] > END_MM
    assert t[e] - T0 < 1.0 + 2.5 + 0.5


def test_rise_before_descent_uses_highest_point() -> None:
    t_low, mm_low = tof_track(1.0, mm=30.0)
    t, mm = descent_tof()
    t_all = np.concatenate([t_low, t + 1.025])
    mm_all = np.concatenate([mm_low, mm])
    r = analyze_reach(t_all, mm_all, [])
    assert len(r.attempts) == 1 and 250 < r.attempts[0].mm[0] < 300


def test_window_without_descent_is_skipped() -> None:
    t_flat, mm_flat = tof_track(3.0, mm=300.0)
    t, mm = descent_tof()
    t_all = np.concatenate([t_flat, t + 3.025])
    mm_all = np.concatenate([mm_flat, mm])
    r = analyze_reach(t_all, mm_all, [T0 + 3.0])
    assert len(r.attempts) == 1


def test_all_invalid_raises_no_descent() -> None:
    t, _ = descent_tof()
    with pytest.raises(AnalysisError) as e:
        analyze_reach(t, np.full(t.size, np.nan), [])
    assert e.value.code == "no_descent_detected"


@pytest.mark.parametrize(("fs", "n"), [(40.0, 13), (50.0, 15), (10.0, 5), (100.0, 31)])
def test_sg_window_is_nearest_odd_at_least_five(fs: float, n: int) -> None:
    assert _sg_window(fs) == n
