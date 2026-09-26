"""Numeric definitions shared by the engine (model_spec.md §12.5)."""

import numpy as np
from numpy.typing import ArrayLike, NDArray

F64 = NDArray[np.float64]

# A vector whose population SD is at most this times max(1, max |x|) counts as constant.
CONSTANT_TOLERANCE = 1e-12


def standardise(values: ArrayLike) -> F64:
    """Return (x - mean) / SD with the population SD (ddof = 0); a constant vector maps to zeros."""
    x = np.asarray(values, dtype=np.float64)
    if x.size == 0:
        return x.copy()
    sd = float(x.std())
    if sd <= CONSTANT_TOLERANCE * max(1.0, float(np.max(np.abs(x)))):
        return np.zeros_like(x)
    return (x - x.mean()) / sd


def standardise_rows(values: F64) -> F64:
    """Standardise each row of a matrix as `standardise` does; constant rows map to zeros."""
    mean = values.mean(axis=1, keepdims=True)
    sd = values.std(axis=1, keepdims=True)
    scale = np.maximum(1.0, np.max(np.abs(values), axis=1, keepdims=True))
    constant = sd <= CONSTANT_TOLERANCE * scale
    return np.where(constant, 0.0, (values - mean) / np.where(constant, 1.0, sd))


def largest_remainder(total: int, weights: ArrayLike, tie_keys: ArrayLike | None = None) -> NDArray[np.int64]:
    """Split `total` units in proportion to `weights` by the largest-remainder (Hamilton) method.

    Entry k gets floor(total * w_k / sum(w)); the leftover units go to the largest fractional parts, ties broken by
    the smaller tie key (default: the lower index).
    """
    w = np.asarray(weights, dtype=np.float64)
    if total < 0 or w.ndim != 1 or w.size == 0 or np.any(w < 0) or not np.all(np.isfinite(w)) or w.sum() <= 0:
        raise ValueError("largest_remainder needs a non-negative total and non-negative weights with a positive sum")
    quota = total * w / w.sum()
    counts = np.floor(quota).astype(np.int64)
    leftover = int(min(max(total - int(counts.sum()), 0), w.size))
    keys = np.arange(w.size) if tie_keys is None else np.asarray(tie_keys, dtype=np.float64)
    order = np.lexsort((keys, -(quota - counts)))
    counts[order[:leftover]] += 1
    return counts


def quantiles(values: ArrayLike) -> F64:
    """Return each value's 0-based ascending rank (ties by index) divided by n - 1; a single value gets 1."""
    x = np.asarray(values, dtype=np.float64)
    n = x.size
    if n == 1:
        return np.ones(1)
    ranks = np.empty(n, dtype=np.float64)
    ranks[np.argsort(x, kind="stable")] = np.arange(n, dtype=np.float64)
    return ranks / (n - 1)


def correlation(x: ArrayLike, y: ArrayLike) -> float | None:
    """Return the Pearson correlation of two vectors, or None when either is constant or they are too short."""
    a = np.asarray(x, dtype=np.float64)
    b = np.asarray(y, dtype=np.float64)
    if a.size < 2:
        return None
    za, zb = standardise(a), standardise(b)
    if not za.any() or not zb.any():
        return None
    return float(np.mean(za * zb))
