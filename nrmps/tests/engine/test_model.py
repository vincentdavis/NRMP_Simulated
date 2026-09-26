"""Utilities, observation, ranks and the pre-interview run: acceptance tests 1-6 of model_spec.md §9."""

import itertools

import numpy as np
import pytest

from nrmps.engine.persistence import (
    population_digest,
    population_from_npz,
    population_to_npz,
    results_from_npz,
    results_to_npz,
)
from nrmps.engine.pipeline import agent_view, blocks, run_pre_interview, side_block
from nrmps.engine.population import generate_population
from nrmps.engine.rank import rank_of, rank_rows
from nrmps.engine.rng import Stream, pair_uniforms
from nrmps.engine.utility import build_market
from nrmps.params import SimulationParams, canonical_json


def _params(**groups) -> SimulationParams:
    return SimulationParams.model_validate(groups)


def _full(params: SimulationParams, seed: int, side: str = "applicants"):
    """Return (true, observed, true ranks, observed ranks) for every agent of one side."""
    population = generate_population(params, seed)
    model = build_market(params, population, seed)
    if side == "applicants":
        agents = np.arange(population.n_applicants)
        return side_block(model.applicants, model.applicant_view, agents, 0)
    return side_block(model.programs, model.program_view, np.arange(population.n_programs), 0)


# --- 1. Determinism ---------------------------------------------------------------------------------------------------


def test_same_seed_gives_byte_identical_results():
    params = _params(market={"n_applicants": 400})
    first = run_pre_interview(params, 2024)
    second = run_pre_interview(params, 2024)
    assert population_to_npz(first.population) == population_to_npz(second.population)
    assert canonical_json(first.metrics) == canonical_json(second.metrics)
    assert results_to_npz(first.applicants, first.programs) == results_to_npz(second.applicants, second.programs)
    assert np.array_equal(_full(params, 2024)[0], _full(params, 2024)[0])


def test_different_seeds_give_different_markets():
    params = _params(market={"n_applicants": 200})
    first, second = run_pre_interview(params, 1), run_pre_interview(params, 2)
    assert population_digest(first.population) != population_digest(second.population)


def test_blocks_do_not_change_results():
    params = _params(market={"n_applicants": 300})
    whole = run_pre_interview(params, 5)
    pieces = run_pre_interview(params, 5, block_pairs=317)
    for side in ("applicants", "programs"):
        a, b = getattr(whole, side), getattr(pieces, side)
        assert np.array_equal(a.first_choice, b.first_choice)
        assert np.array_equal(a.fidelity, b.fidelity, equal_nan=True)
    assert whole.metrics["applicants"]["consensus"]["true_utility_correlation"] == pytest.approx(
        pieces.metrics["applicants"]["consensus"]["true_utility_correlation"], abs=1e-12
    )


def test_a_block_equals_the_same_entries_of_the_full_matrix():
    params = _params(market={"n_applicants": 120}, info={"halo_share": 0.3, "visibility_heteroskedasticity": 0.5})
    population = generate_population(params, 9)
    model = build_market(params, population, 9)
    full_u, full_obs, _, _ = side_block(model.applicants, model.applicant_view, np.arange(120), 0)
    agents, targets = np.array([3, 50, 77]), np.array([0, 5, 6, 16])
    block = model.applicants.utilities(agents, targets)
    assert np.array_equal(block, full_u[np.ix_(agents, targets)])
    observed = model.applicant_view.observe(block, agents, targets)
    assert np.array_equal(observed, full_obs[np.ix_(agents, targets)])
    full_v, _, _, _ = side_block(model.programs, model.program_view, np.arange(population.n_programs), 0)
    assert np.array_equal(model.programs.utilities(np.array([4]), np.array([7, 8])), full_v[np.ix_([4], [7, 8])])


def test_progress_is_reported_in_pairs():
    calls = []
    params = _params(market={"n_applicants": 100})
    run_pre_interview(params, 1, block_pairs=500, progress=lambda done, total: calls.append((done, total)))
    pairs = 100 * params.n_programs()
    assert calls[-1] == (2 * pairs, 2 * pairs)
    assert all(a[0] < b[0] for a, b in itertools.pairwise(calls))


# --- 2. Common random numbers -------------------------------------------------------------------------------------


def test_changing_noise_keeps_the_population_and_true_utilities():
    base = _params(market={"n_applicants": 300})
    noisier = _params(market={"n_applicants": 300}, info={"applicant_pre_noise_sd": 1.2, "program_pre_noise_sd": 0.1})
    a, b = run_pre_interview(base, 77), run_pre_interview(noisier, 77)
    assert population_digest(a.population) == population_digest(b.population)
    for side in ("applicants", "programs"):
        base_true, base_obs, _, _ = _full(base, 77, side)
        other_true, other_obs, _, _ = _full(noisier, 77, side)
        assert np.array_equal(base_true, other_true)
        assert not np.array_equal(base_obs, other_obs)


def test_changing_agreement_keeps_the_population():
    base = _params(market={"n_applicants": 300})
    other = _params(market={"n_applicants": 300}, prefs={"applicant_pref_correlation": 0.2, "taste_share": 0.9})
    assert population_digest(generate_population(base, 3)) == population_digest(generate_population(other, 3))


def test_idiosyncratic_fit_does_not_depend_on_the_market_shape():
    # With rho = 0 and tau = 0 an applicant's utility is exactly the idiosyncratic draw of the pair.
    prefs = {"applicant_pref_correlation": 0, "taste_share": 0}
    small = _params(market={"n_applicants": 100}, prefs=prefs)
    large = _params(market={"n_applicants": 200, "n_programs": small.n_programs() + 5}, prefs=prefs)
    m = small.n_programs()
    large_model = build_market(large, generate_population(large, 4), 4)
    assert np.array_equal(_full(small, 4)[0], large_model.applicants.utilities(np.arange(100), np.arange(m)))


# --- 3. Exactness -----------------------------------------------------------------------------------------------------


def test_zero_noise_observes_the_truth_exactly():
    params = _params(market={"n_applicants": 200}, info={"applicant_pre_noise_sd": 0, "program_pre_noise_sd": 0})
    for side in ("applicants", "programs"):
        true, observed, true_ranks, observed_ranks = _full(params, 8, side)
        assert np.array_equal(true, observed)
        assert np.array_equal(true_ranks, observed_ranks)
    result = run_pre_interview(params, 8)
    assert result.metrics["applicants"]["fidelity"]["spearman_mean"] == 1.0


@pytest.mark.parametrize("sigma", [0.25, 0.5, 1.0])
def test_pooled_correlation_matches_the_reliability(sigma):
    params = _params(
        market={"n_applicants": 2000}, info={"applicant_pre_noise_sd": sigma, "program_pre_noise_sd": sigma}
    )
    fidelity = run_pre_interview(params, 10).metrics["applicants"]["fidelity"]
    assert fidelity["expected_correlation"] == pytest.approx(np.sqrt(1 / (1 + sigma**2)))
    assert fidelity["pooled_correlation"] == pytest.approx(np.sqrt(1 / (1 + sigma**2)), abs=0.01)


def test_visibility_makes_less_known_programs_noisier():
    params = _params(market={"n_applicants": 1000}, info={"visibility_heteroskedasticity": 1.0})
    model = build_market(params, generate_population(params, 11), 11)
    scale = model.applicant_view.scale
    quality = generate_population(params, 11).programs.quality
    assert scale[np.argmax(quality)] == pytest.approx(0.5)
    assert scale[np.argmin(quality)] == pytest.approx(1.0)
    expected = 1 / np.sqrt(1 + np.mean(scale**2))
    assert run_pre_interview(params, 11).metrics["applicants"]["fidelity"]["expected_correlation"] == pytest.approx(
        expected
    )


@pytest.mark.parametrize("psi", [0.0, 0.8])
def test_halo_errors_are_shared_by_everyone_judging_a_program(psi):
    params = _params(market={"n_applicants": 400, "n_programs": 300}, info={"halo_share": psi})
    true, observed, _, _ = _full(params, 12)
    errors = observed - true  # applicants x programs
    pairwise = np.corrcoef(errors)[np.triu_indices(errors.shape[0], k=1)]
    assert pairwise.mean() == pytest.approx(psi, abs=0.05)


# --- 4. The correlation knob -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("rho", [0.0, 0.2, 0.4, 0.6, 0.8])
def test_mean_pairwise_correlation_equals_rho(rho):
    params = _params(
        market={"n_applicants": 500, "n_programs": 100},
        prefs={"applicant_pref_correlation": rho, "program_pref_correlation": rho},
    )
    metrics = run_pre_interview(params, 13).metrics
    tolerance = 0.01 if rho == 0 else 0.02
    assert metrics["applicants"]["consensus"]["true_utility_correlation"] == pytest.approx(rho, abs=tolerance)
    assert metrics["programs"]["consensus"]["true_utility_correlation"] == pytest.approx(rho, abs=tolerance)


def test_full_agreement_without_noise_gives_identical_rankings():
    params = _params(
        market={"n_applicants": 300},
        prefs={"applicant_pref_correlation": 1, "program_pref_correlation": 1},
        info={"applicant_pre_noise_sd": 0, "program_pre_noise_sd": 0},
    )
    for side in ("applicants", "programs"):
        ranks = _full(params, 14, side)[3]
        assert np.all(ranks == ranks[0])


@pytest.mark.parametrize("side", ["applicants", "programs"])
def test_taste_terms_are_uncorrelated_with_the_common_term_for_every_agent(side):
    params = _params(market={"n_applicants": 400})
    model = build_market(params, generate_population(params, 15), 15)
    side_model = getattr(model, side)
    agents = np.arange(side_model.n_agents)
    taste = side_model.taste(agents, np.arange(side_model.n_targets))
    common = side_model.common - side_model.common.mean()
    correlations = (taste - taste.mean(axis=1, keepdims=True)) @ common / side_model.n_targets
    assert np.abs(correlations).max() < 1e-9
    assert np.allclose(taste.mean(axis=1), 0, atol=1e-9)
    assert np.allclose(taste.std(axis=1), 1, atol=1e-9)


def test_one_attribute_means_no_taste_term():
    params = _params(
        market={"n_applicants": 100},
        programs={"attributes": [{"key": "reputation", "corr_with_quality": 0.9, "applicant_weight_prior": 1}]},
    )
    model = build_market(params, generate_population(params, 16), 16)
    assert not model.applicants.has_taste.any()
    assert np.all(model.applicants.sqrt_one_minus_tau == 1.0)


# --- 5. Moments -------------------------------------------------------------------------------------------------------


def test_each_agents_utilities_have_unit_variance():
    params = _params(market={"n_applicants": 500, "n_programs": 300})
    for side in ("applicants", "programs"):
        true = _full(params, 17, side)[0]
        variances = true.var(axis=1)
        assert variances.mean() == pytest.approx(1, abs=0.02)
        assert variances.std() < 0.15


# --- 6. Ranks ---------------------------------------------------------------------------------------------------------


def test_ranks_are_permutations():
    params = _params(market={"n_applicants": 250})
    for side in ("applicants", "programs"):
        _true, _observed, true_ranks, observed_ranks = _full(params, 18, side)
        expected = np.arange(1, true_ranks.shape[1] + 1)
        assert np.array_equal(np.sort(true_ranks, axis=1), np.broadcast_to(expected, true_ranks.shape))
        assert np.array_equal(np.sort(observed_ranks, axis=1), np.broadcast_to(expected, observed_ranks.shape))


def _tied_scores() -> np.ndarray:
    scores = np.tile(np.array([3.0, 1.0, 1.0, 1.0, 2.0, 1.0]), (40, 1))
    scores[0] = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]  # one row without ties
    return scores


def _keys(seed: int):
    def keys(rows):
        return pair_uniforms(seed, Stream.TIE_A, 0, rows[:, None], np.arange(6)[None, :])

    return keys


def test_ties_are_broken_by_seed_and_repeat_for_the_same_seed():
    scores = _tied_scores()
    first = rank_rows(scores, _keys(1))
    assert np.array_equal(first, rank_rows(scores, _keys(1)))
    assert not np.array_equal(first, rank_rows(scores, _keys(2)))
    assert first[0].tolist() == [6, 5, 4, 3, 2, 1]
    assert np.all(first[1:, 0] == 1)
    assert np.all(first[1:, 4] == 2)
    for row in first[1:]:
        assert sorted(row[[1, 2, 3, 5]].tolist()) == [3, 4, 5, 6]


def test_tied_ranks_equal_a_full_lexsort():
    scores = _tied_scores()
    keys = _keys(3)(np.arange(40))
    expected = np.empty_like(scores, dtype=np.int32)
    order = np.lexsort((keys, -scores), axis=1)
    np.put_along_axis(expected, order, np.arange(1, 7)[None, :], axis=1)
    assert np.array_equal(rank_rows(scores, _keys(3)), expected)
    for row in range(40):
        for column in range(6):
            assert rank_of(scores[row], keys[row], column) == expected[row, column]


# --- Persistence and drill-down ---------------------------------------------------------------------------------------


def test_population_and_results_round_trip():
    params = _params(market={"n_applicants": 150}, programs={"tiers": [{"name": "top", "share": 1.0}]})
    result = run_pre_interview(params, 19)
    data = population_to_npz(result.population)
    loaded = population_from_npz(data)
    assert population_digest(loaded) == population_digest(result.population)
    assert population_to_npz(loaded) == data
    again = run_pre_interview(params, 19, population=loaded)
    assert canonical_json(again.metrics) == canonical_json(result.metrics)
    applicants, programs = results_from_npz(results_to_npz(result.applicants, result.programs))
    assert np.array_equal(applicants.popularity, result.applicants.popularity)
    assert np.array_equal(programs.fidelity, result.programs.fidelity, equal_nan=True)


def test_agent_view_recomputes_one_row():
    params = _params(market={"n_applicants": 150})
    population = generate_population(params, 20)
    model = build_market(params, population, 20)
    true, _observed, _true_ranks, observed_ranks = side_block(
        model.programs, model.program_view, np.arange(population.n_programs), 0
    )
    view = agent_view(model, 7, applicant=False)
    assert np.array_equal(view.true, true[7])
    assert np.array_equal(view.observed_rank, observed_ranks[7])
    result = run_pre_interview(params, 20, population=population)
    assert result.programs.first_choice[7] == int(np.argmin(observed_ranks[7]))


def test_blocks_cover_the_range():
    assert [b.tolist() for b in blocks(7, 3)] == [[0, 1, 2], [3, 4, 5], [6]]
    assert blocks(0, 3) == []
