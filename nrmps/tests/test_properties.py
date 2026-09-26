"""Property-based tests (plan steps 1.1 and 2.2): strict ranking and the population CSV round trip."""

import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from hypothesis import given, settings
from hypothesis import strategies as st

from nrmps.engine.population import generate_population
from nrmps.engine.rank import rank_rows
from nrmps.params import SimulationParams
from nrmps.population_csv import applicant_side, parse_population_csv, population_csv_lines, program_side


@st.composite
def ranking_problems(draw):
    """A score matrix with likely ties, and tie keys (also with ties)."""
    rows, columns = draw(st.integers(1, 8)), draw(st.integers(1, 12))
    values = st.sampled_from([0.0, -0.0, 0.25, 1.0]) | st.floats(-2, 2, allow_nan=False)
    scores = np.array(draw(st.lists(values, min_size=rows * columns, max_size=rows * columns))).reshape(rows, columns)
    keys = np.array(
        draw(st.lists(st.sampled_from([0.1, 0.5, 0.9]), min_size=rows * columns, max_size=rows * columns))
    ).reshape(rows, columns)
    return scores, keys


@settings(max_examples=300, deadline=None)
@given(ranking_problems())
def test_ranks_are_permutations_ordered_by_score_then_key_then_index(problem):
    scores, keys = problem
    ranks = rank_rows(scores, lambda rows: keys[rows])
    rows, columns = scores.shape
    for row in range(rows):
        assert sorted(ranks[row].tolist()) == list(range(1, columns + 1))
        order = sorted(range(columns), key=lambda j: (-scores[row, j], keys[row, j], j))
        assert [int(ranks[row, j]) for j in order] == list(range(1, columns + 1))


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(0, 2**63 - 1), n=st.integers(10, 60), size=st.floats(1, 10))
def test_csv_download_uploads_back_unchanged(seed, n, size):
    params = SimulationParams.model_validate(
        {"market": {"n_applicants": n, "program_size_mean": size}, "run": {"seed": seed}}
    )
    population = generate_population(params, seed)
    for side, original, convert in (
        ("applicants", population.applicants, applicant_side),
        ("programs", population.programs, program_side),
    ):
        text = "".join(population_csv_lines(original)).encode()
        upload = parse_population_csv(SimpleUploadedFile("f.csv", text), side, params)
        again = convert(upload, params, seed)
        assert "".join(population_csv_lines(again)).encode() == text
        assert np.array_equal(again.attributes, original.attributes)
        assert np.array_equal(again.weights, original.weights)
