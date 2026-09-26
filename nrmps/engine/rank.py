"""Strict rankings with seeded tie-breaking (model_spec.md §8 and §12.8)."""

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

F64 = NDArray[np.float64]
I32 = NDArray[np.int32]
Indices = NDArray[np.int64]

# Returns the tie keys (uniforms) of the given rows of the block being ranked, shaped (rows, columns).
TieKeys = Callable[[Indices], F64]


def rank_rows(scores: F64, tie_keys: TieKeys) -> I32:
    """Rank each row of `scores` from 1 (highest) to the row length, with no ties.

    Equal scores are ordered by the smaller tie key, then by the lower column index, exactly as
    `np.lexsort((keys, -scores))` over the whole row. Tie keys are only drawn for rows that contain an exact tie.
    """
    rows, columns = scores.shape
    order = np.argsort(-scores, axis=1, kind="stable")
    if columns > 1:
        ordered = np.take_along_axis(scores, order, axis=1)
        tied = np.flatnonzero((ordered[:, 1:] == ordered[:, :-1]).any(axis=1))
        if tied.size:
            keys = tie_keys(tied.astype(np.int64))
            order[tied] = np.lexsort((keys, -scores[tied]), axis=1)
    ranks = np.empty((rows, columns), dtype=np.int32)
    np.put_along_axis(ranks, order, np.arange(1, columns + 1, dtype=np.int32)[None, :], axis=1)
    return ranks


def rank_of(scores: F64, keys: F64, index: int) -> int:
    """Return the rank of entry `index` within one row (for drill-down views), consistent with `rank_rows`.

    1 + #{higher score} + #{equal score, smaller key} + #{equal score and key, smaller index}.
    """
    score, key = scores[index], keys[index]
    higher = int(np.count_nonzero(scores > score))
    equal = scores == score
    smaller_key = int(np.count_nonzero(equal & (keys < key)))
    same_key_before = int(np.count_nonzero(equal[:index] & (keys[:index] == key)))
    return 1 + higher + smaller_key + same_key_before
