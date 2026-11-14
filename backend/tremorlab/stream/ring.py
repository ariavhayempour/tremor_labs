"""Fixed-capacity ring buffer of timestamped samples."""

import numpy as np
from numpy.typing import NDArray


class RingBuffer:
    """Keeps the newest `capacity` samples; width 0 stores 1-D values, else (N, width) rows."""

    def __init__(self, capacity: int, width: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._width = width
        self._t = np.empty(capacity, dtype=np.float64)
        shape = (capacity,) if width == 0 else (capacity, width)
        self._x = np.empty(shape, dtype=np.float64)
        self._head = 0  # next write position
        self._size = 0

    def append(self, t: NDArray[np.float64], x: NDArray[np.float64]) -> None:
        """Append samples: t (N,) s, x (N,) or (N, width)."""
        expected = (len(t),) if self._width == 0 else (len(t), self._width)
        if x.shape != expected:
            raise ValueError(f"expected x shape {expected}, got {x.shape}")
        if len(t) > self._capacity:
            t, x = t[-self._capacity :], x[-self._capacity :]
        idx = (self._head + np.arange(len(t))) % self._capacity
        self._t[idx] = t
        self._x[idx] = x
        self._head = (self._head + len(t)) % self._capacity
        self._size = min(self._size + len(t), self._capacity)

    def _ordered(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        idx = (self._head - self._size + np.arange(self._size)) % self._capacity
        return self._t[idx], self._x[idx]

    def window(self, seconds: float) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Samples with t within `seconds` before the newest t (exclusive of the far edge)."""
        t, x = self._ordered()
        if len(t) == 0:
            return t, x
        keep = t > t[-1] - seconds
        return t[keep], x[keep]

    def latest(self) -> tuple[float, NDArray[np.float64]] | None:
        if self._size == 0:
            return None
        i = (self._head - 1) % self._capacity
        return float(self._t[i]), np.asarray(self._x[i])

    def clear(self) -> None:
        self._head = 0
        self._size = 0
