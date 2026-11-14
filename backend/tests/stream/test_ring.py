import numpy as np
import pytest

from tremorlab.stream.ring import RingBuffer


def test_ring_window_returns_last_seconds() -> None:
    ring = RingBuffer(3000, 6)
    t = np.arange(1000) / 100.0
    ring.append(t, np.tile(t[:, None], (1, 6)))
    wt, wx = ring.window(2.0)
    assert len(wt) == 200 and wx.shape == (200, 6)
    assert wt[0] == pytest.approx(8.0) and wt[-1] == pytest.approx(9.99)
    assert np.array_equal(wx[:, 0], wt)


def test_ring_wraps_at_capacity() -> None:
    ring = RingBuffer(50, 0)
    for k in range(12):
        t = (np.arange(10) + 10 * k) / 100.0
        ring.append(t, t * 2)
    wt, wx = ring.window(100.0)
    assert len(wt) == 50
    assert np.array_equal(wt, (np.arange(70, 120)) / 100.0)
    assert np.array_equal(wx, wt * 2)


def test_ring_append_larger_than_capacity_keeps_newest() -> None:
    ring = RingBuffer(10, 0)
    t = np.arange(25, dtype=np.float64)
    ring.append(t, t)
    wt, _ = ring.window(1e9)
    assert np.array_equal(wt, np.arange(15, 25))


def test_ring_latest_and_clear() -> None:
    ring = RingBuffer(10, 0)
    assert ring.latest() is None
    assert len(ring.window(1.0)[0]) == 0
    ring.append(np.array([1.0, 2.0]), np.array([10.0, 20.0]))
    latest = ring.latest()
    assert latest is not None and latest[0] == 2.0 and float(latest[1]) == 20.0
    ring.clear()
    assert ring.latest() is None


def test_ring_width_mismatch_raises() -> None:
    ring = RingBuffer(10, 3)
    with pytest.raises(ValueError):
        ring.append(np.array([1.0]), np.zeros((1, 2)))
