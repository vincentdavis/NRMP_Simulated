"""Random streams: Philox4x32-10 known answers, the uniform and normal recipes, stream independence (§12.1-12.4)."""

import numpy as np
import pytest

from nrmps.engine.rng import (
    POPULATION_STREAMS,
    Stream,
    check_seed,
    pair_normals,
    pair_uniforms,
    philox4x32,
    replicate_for,
    seed_key,
    stream_generator,
    uniform53,
)


def _hex(words) -> str:
    return " ".join(f"{int(word):08x}" for word in words)


# Random123 kat_vectors for philox4x32_10 (model_spec.md §12.3).
KNOWN_ANSWERS = [
    ((0, 0, 0, 0), (0, 0), "6627e8d5 e169c58d bc57ac4c 9b00dbd8"),
    ((0xFFFFFFFF,) * 4, (0xFFFFFFFF, 0xFFFFFFFF), "408f276d 41c83b0e a20bc7c6 6d5451fd"),
    ((0x243F6A88, 0x85A308D3, 0x13198A2E, 0x03707344), (0xA4093822, 0x299F31D0), "d16cfe09 94fdcceb 5001e420 24126ea1"),
]


@pytest.mark.parametrize(("counter", "key", "expected"), KNOWN_ANSWERS)
def test_philox_known_answers(counter, key, expected):
    assert _hex(philox4x32(counter, key)) == expected


def test_philox_vectorised_equals_scalar():
    rng = np.random.default_rng(1)
    counters = rng.integers(0, 2**32, size=(4, 50), dtype=np.uint64)
    key = (0x12345678, 0x9ABCDEF0)
    words = philox4x32(tuple(counters), key)
    for index in range(50):
        scalar = philox4x32(tuple(int(c[index]) for c in counters), key)
        assert [int(w) for w in scalar] == [int(w[index]) for w in words]


def test_uniform_mapping_edges():
    top = np.uint64(0xFFFFFFFF)
    zero = np.uint64(0)
    # The largest 53-bit integer rounds half to even to exactly 1.0; the smallest value is 2^-54.
    assert uniform53(np.array([top]), np.array([top]))[0] == 1.0
    assert uniform53(np.array([zero]), np.array([zero]))[0] == 2.0**-54
    # A value just below the top stays below 1.
    assert uniform53(np.array([top]), np.array([np.uint64(0xFFFFFF7F)]))[0] < 1.0


def test_uniforms_and_normals_have_the_right_moments():
    i = np.arange(400)[:, None]
    j = np.arange(500)[None, :]
    u = pair_uniforms(7, Stream.TIE_A, 0, i, j)
    z = pair_normals(7, Stream.IDIO_A, 0, i, j)
    assert u.shape == z.shape == (400, 500)
    assert u.min() > 0
    assert u.max() <= 1
    # Tolerances of 4.5 standard errors (200,000 draws).
    se = 1 / np.sqrt(u.size)
    assert abs(u.mean() - 0.5) < 4.5 * se * np.sqrt(1 / 12)
    assert abs(z.mean()) < 4.5 * se
    assert abs(z.std() - 1) < 4.5 * se * np.sqrt(0.5)
    assert np.abs(z).max() <= np.sqrt(108 * np.log(2))


def test_pair_draws_do_not_depend_on_the_block():
    full = pair_normals(99, Stream.PRE_A, 3, np.arange(30)[:, None], np.arange(20)[None, :])
    block = pair_normals(99, Stream.PRE_A, 3, np.arange(10, 17)[:, None], np.arange(5, 9)[None, :])
    single = pair_normals(99, Stream.PRE_A, 3, 12, 6)
    assert np.array_equal(block, full[10:17, 5:9])
    assert single == full[12, 6]


def test_pair_draws_differ_by_stream_replicate_seed_and_pair():
    i, j = np.arange(50)[:, None], np.arange(50)[None, :]
    base = pair_normals(5, Stream.IDIO_A, 0, i, j)
    for other in (
        pair_normals(5, Stream.IDIO_P, 0, i, j),
        pair_normals(5, Stream.IDIO_A, 1, i, j),
        pair_normals(6, Stream.IDIO_A, 0, i, j),
        pair_normals(5, Stream.IDIO_A, 0, j, i),
    ):
        assert abs(np.corrcoef(base.ravel(), other.ravel())[0, 1]) < 0.06


def test_seed_key_uses_both_halves():
    assert seed_key(2**40 + 5) == (5, 2**8)
    assert not np.array_equal(pair_uniforms(5, Stream.TIE_A, 0, 1, 1), pair_uniforms(2**40 + 5, Stream.TIE_A, 0, 1, 1))


@pytest.mark.parametrize("seed", [-1, 2**63, 1.5, "3", True])
def test_bad_seeds_are_rejected(seed):
    with pytest.raises(ValueError, match="seed"):
        check_seed(seed)


def test_stream_generator_is_child_stream_of_child_replicate():
    child = np.random.SeedSequence(123).spawn(3)[2].spawn(6)[5]
    expected = np.random.Generator(np.random.PCG64(child)).random(4)
    assert np.array_equal(stream_generator(123, Stream.WEIGHTS_P, replicate=2).random(4), expected)


def test_population_streams_use_replicate_zero_unless_resampled():
    assert {
        Stream.POP_A,
        Stream.POP_P,
        Stream.CAP,
        Stream.WEIGHTS_A,
        Stream.WEIGHTS_P,
        Stream.IDIO_A,
        Stream.IDIO_P,
    } == POPULATION_STREAMS
    assert replicate_for(Stream.IDIO_A, 4, resample_population=False) == 0
    assert replicate_for(Stream.IDIO_A, 4, resample_population=True) == 4
    assert replicate_for(Stream.PRE_A, 4, resample_population=False) == 4
