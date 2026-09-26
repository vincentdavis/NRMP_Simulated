"""Random streams (model_spec.md §3 and §12.1-12.4).

Population-level draws come from numpy Generators, one per (seed, replicate, stream). Pair-level draws come from the
counter-based generator Philox4x32-10, keyed by the seed with counter (i, j, stream, replicate), where i is always the
applicant index and j the program index. Any pair's draw can therefore be computed on its own, in any block and in any
order, and a JavaScript port can reproduce it.
"""

from enum import IntEnum

import numpy as np
from numpy.typing import ArrayLike, NDArray

U64 = NDArray[np.uint64]
F64 = NDArray[np.float64]


class Stream(IntEnum):
    """Stream IDs (§12.1). They are never renumbered or reused."""

    POP_A = 1
    POP_P = 2
    CAP = 3
    WEIGHTS_A = 4
    WEIGHTS_P = 5
    IDIO_A = 6
    IDIO_P = 7
    PRE_A = 8
    PRE_P = 9
    APPS = 10
    SIGNALS = 11
    INVITES = 12
    ACCEPT = 13
    FIT = 14
    POST_A = 15
    POST_P = 16
    TIE_A = 17
    TIE_P = 18
    SOAP = 19
    HALO_A = 20
    HALO_P = 21


# Streams that make up the population and the true utilities; they use replicate 0 unless every replicate draws a
# new population (§3).
POPULATION_STREAMS = frozenset(
    {Stream.POP_A, Stream.POP_P, Stream.CAP, Stream.WEIGHTS_A, Stream.WEIGHTS_P, Stream.IDIO_A, Stream.IDIO_P}
)

MAX_SEED = 2**63 - 1


def check_seed(seed: int) -> int:
    """Return `seed` if it is an integer in [0, 2^63 - 1], else raise ValueError."""
    if isinstance(seed, bool) or not isinstance(seed, int | np.integer) or not 0 <= int(seed) <= MAX_SEED:
        raise ValueError(f"The seed must be an integer from 0 to {MAX_SEED}; got {seed!r}.")
    return int(seed)


def replicate_for(stream: Stream, replicate: int, resample_population: bool) -> int:
    """Return the replicate a stream draws from: 0 for population streams unless the population is resampled."""
    if stream in POPULATION_STREAMS and not resample_population:
        return 0
    return replicate


def stream_generator(seed: int, stream: Stream, replicate: int = 0) -> np.random.Generator:
    """Return the population-level Generator for (seed, replicate, stream) (§12.2).

    It is child `stream` of child `replicate` of `SeedSequence(seed)`.
    """
    sequence = np.random.SeedSequence(check_seed(seed), spawn_key=(replicate, int(stream)))
    return np.random.Generator(np.random.PCG64(sequence))


# --- Philox4x32-10 (§12.3) ----------------------------------------------------------------------------------------

_M0 = np.uint64(0xD2511F53)
_M1 = np.uint64(0xCD9E8D57)
_W0 = 0x9E3779B9
_W1 = 0xBB67AE85
_MASK = np.uint64(0xFFFFFFFF)
_SHIFT = np.uint64(32)
ROUNDS = 10


def _words(value: ArrayLike) -> U64:
    array = np.asarray(value)
    if array.dtype.kind == "f":
        raise TypeError("Philox counters must be integers")
    return array.astype(np.uint64, copy=False)


def philox4x32(
    counter: tuple[ArrayLike, ArrayLike, ArrayLike, ArrayLike], key: tuple[int, int], rounds: int = ROUNDS
) -> tuple[U64, U64, U64, U64]:
    """Apply Philox4x32 to counters (c0, c1, c2, c3) with key (k0, k1); return the four output words.

    The counter words are 32-bit values in integer arrays that broadcast against each other; the result has the
    broadcast shape. Products are formed in 64 bits, so the high and low words of each 32 x 32-bit product are exact.
    """
    c0, c1, c2, c3 = (_words(word) for word in counter)
    k0, k1 = int(key[0]) & 0xFFFFFFFF, int(key[1]) & 0xFFFFFFFF
    for round_index in range(rounds):
        if round_index:
            k0 = (k0 + _W0) & 0xFFFFFFFF
            k1 = (k1 + _W1) & 0xFFFFFFFF
        p0 = _M0 * c0
        p1 = _M1 * c2
        c0, c1, c2, c3 = (
            (p1 >> _SHIFT) ^ c1 ^ np.uint64(k0),
            p1 & _MASK,
            (p0 >> _SHIFT) ^ c3 ^ np.uint64(k1),
            p0 & _MASK,
        )
    shape = np.broadcast_shapes(c0.shape, c1.shape, c2.shape, c3.shape)
    return tuple(np.broadcast_to(word, shape) for word in (c0, c1, c2, c3))  # type: ignore[return-value]


def seed_key(seed: int) -> tuple[int, int]:
    """Return the Philox key of a seed: (low 32 bits, high bits)."""
    seed = check_seed(seed)
    return seed & 0xFFFFFFFF, seed >> 32


# --- Uniform and normal mapping (§12.4) ---------------------------------------------------------------------------

_TWO_26 = np.uint64(67108864)
_TWO_53 = 9007199254740992.0
TWO_PI = 6.283185307179586


def uniform53(a: U64, b: U64) -> F64:
    """Map two 32-bit words to a double in (0, 1]: ((a >> 5) * 2^26 + (b >> 6) + 0.5) / 2^53."""
    whole = (a >> np.uint64(5)) * _TWO_26 + (b >> np.uint64(6))
    return (whole.astype(np.float64) + 0.5) / _TWO_53


def normal_from_words(w0: U64, w1: U64, w2: U64, w3: U64) -> F64:
    """Box-Muller: sqrt(-2 log u1) cos(2 pi u2) with u1 = uniform(w0, w1) and u2 = uniform(w2, w3)."""
    return np.sqrt(-2.0 * np.log(uniform53(w0, w1))) * np.cos(TWO_PI * uniform53(w2, w3))


def pair_uniforms(seed: int, stream: Stream, replicate: int, i: ArrayLike, j: ArrayLike) -> F64:
    """Return the pair-level uniforms of `stream` for applicants `i` and programs `j` (broadcast together)."""
    w0, w1, _, _ = philox4x32((i, j, int(stream), replicate), seed_key(seed))
    return uniform53(w0, w1)


def pair_normals(seed: int, stream: Stream, replicate: int, i: ArrayLike, j: ArrayLike) -> F64:
    """Return the pair-level standard normals of `stream` for applicants `i` and programs `j` (broadcast together)."""
    return normal_from_words(*philox4x32((i, j, int(stream), replicate), seed_key(seed)))
