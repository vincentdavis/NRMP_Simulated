"""Population generation and validation (model_spec.md §4, §12.2, §12.5, §12.9; acceptance tests 5 and 8)."""

import dataclasses

import numpy as np
import pytest

from nrmps.engine.numeric import largest_remainder, quantiles, standardise
from nrmps.engine.population import (
    PopulationError,
    dirichlet_rows,
    generate_applicants,
    generate_population,
    generate_programs,
    program_size_attribute,
    validate_population,
)
from nrmps.params import SimulationParams


def _params(**groups) -> SimulationParams:
    return SimulationParams.model_validate(groups)


# --- Numeric definitions -------------------------------------------------------------------------------------------


def test_standardise_uses_the_population_sd_and_maps_constants_to_zero():
    z = standardise([1.0, 2.0, 3.0, 4.0])
    assert z.mean() == pytest.approx(0)
    assert z.std() == pytest.approx(1)
    assert np.array_equal(standardise([5.0, 5.0, 5.0]), np.zeros(3))
    assert np.array_equal(standardise([1e9, 1e9 + 1e-4]), np.zeros(2))  # below 1e-12 x max |x|


def test_largest_remainder_hits_the_total_and_breaks_ties_by_key():
    assert largest_remainder(10, [1, 1, 1]).tolist() == [4, 3, 3]
    assert largest_remainder(10, [1, 1, 1], tie_keys=[0.9, 0.1, 0.5]).tolist() == [3, 4, 3]
    assert largest_remainder(0, [2, 3]).tolist() == [0, 0]
    counts = largest_remainder(1000, [0.44, 0.18, 0.09, 0.25, 0.04])
    assert counts.sum() == 1000
    assert counts.tolist() == [440, 180, 90, 250, 40]


def test_quantiles():
    assert quantiles([3.0, 1.0, 2.0]).tolist() == [1.0, 0.0, 0.5]
    assert quantiles([2.0, 2.0]).tolist() == [0.0, 1.0]  # ties by index
    assert quantiles([7.0]).tolist() == [1.0]


# --- Groups, strength and attributes ------------------------------------------------------------------------------


def test_group_sizes_and_strengths():
    params = _params(market={"n_applicants": 20_000, "n_programs": 2000})
    side = generate_applicants(params, seed=1)
    shares = np.bincount(side.group, minlength=5) / side.size
    assert shares.tolist() == pytest.approx([0.44, 0.18, 0.09, 0.25, 0.04])
    for index, group in enumerate(params.applicants.groups):
        members = side.strength[side.group == index]
        assert members.mean() == pytest.approx(group.strength_mean, abs=4 * group.strength_sd / np.sqrt(members.size))
        assert members.std() == pytest.approx(group.strength_sd, rel=0.06)
    # Labels are shuffled over the indices, not sorted by group.
    assert not np.all(np.diff(side.group) >= 0)


def test_attribute_correlations_follow_the_parameters():
    side = generate_applicants(_params(market={"n_applicants": 20_000, "n_programs": 2000}), seed=2)
    for k, attribute in enumerate(SimulationParams().applicants.attributes):
        realised = np.corrcoef(side.attributes[:, k], standardise(side.strength))[0, 1]
        assert realised == pytest.approx(attribute.corr_with_strength, abs=0.02)
        assert side.attributes[:, k].std() == pytest.approx(1, abs=0.03)


def test_program_size_attribute_is_the_standardised_log_capacity():
    programs = generate_programs(SimulationParams(), seed=3, n_applicants=1000)
    column = programs.keys.index("program_size")
    assert np.array_equal(programs.attributes[:, column], program_size_attribute(programs.capacity))


# --- Capacities (acceptance test 5) -------------------------------------------------------------------------------


@pytest.mark.parametrize("distribution", ["fixed", "lognormal", "shifted_multinomial"])
def test_capacities_add_up_to_the_positions(distribution):
    params = _params(market={"n_applicants": 5000, "program_size_dist": distribution})
    programs = generate_programs(params, seed=4, n_applicants=5000)
    assert programs.capacity.sum() == params.n_positions() == round(5000 / 1.08)
    assert programs.size == params.n_programs()
    assert programs.capacity.min() >= 1
    if distribution == "fixed":
        assert programs.capacity.max() - programs.capacity.min() <= 1


def test_lognormal_sizes_are_right_skewed():
    programs = generate_programs(
        _params(market={"n_applicants": 20_000, "n_programs": 2000}), seed=5, n_applicants=20_000
    )
    assert np.mean(programs.capacity) > np.median(programs.capacity)


def test_realised_tightness_matches_the_request():
    population = generate_population(_params(market={"n_applicants": 3000, "applicants_per_position": 1.25}), seed=6)
    assert population.n_applicants / population.n_positions == pytest.approx(1.25, abs=0.001)


# --- Dirichlet weights (acceptance test 5) --------------------------------------------------------------------------


@pytest.mark.parametrize("concentration", [0.3, 10.0, 1000.0])
def test_dirichlet_mean_and_variance(concentration):
    prior = np.array([0.5, 0.3, 0.2])
    rows = dirichlet_rows(np.random.default_rng(7), 40_000, prior, concentration)
    assert np.allclose(rows.sum(axis=1), 1.0)
    assert rows.min() >= 0
    assert rows.mean(axis=0) == pytest.approx(prior, abs=0.01)
    assert rows.var(axis=0) == pytest.approx(prior * (1 - prior) / (concentration + 1), rel=0.08)


def test_dirichlet_survives_tiny_concentrations():
    rows = dirichlet_rows(np.random.default_rng(8), 1000, np.array([0.998, 0.001, 0.001]), 2.0)
    assert np.all(np.isfinite(rows))
    assert np.allclose(rows.sum(axis=1), 1.0)


def test_one_attribute_gets_weight_one_without_drawing():
    rng = np.random.default_rng(9)
    state = rng.bit_generator.state
    assert np.array_equal(dirichlet_rows(rng, 5, np.array([1.0]), 10.0), np.ones((5, 1)))
    assert rng.bit_generator.state == state


# --- Tiers --------------------------------------------------------------------------------------------------------


def test_tiers_shift_quality():
    tiers = [{"name": "top", "share": 0.2, "quality_mean": 2.0}, {"name": "rest", "share": 0.8, "quality_mean": 0.0}]
    programs = generate_programs(_params(programs={"tiers": tiers}, market={"n_programs": 500}), seed=10)
    assert programs.tier_names == ("top", "rest")
    assert np.bincount(programs.tier).tolist() == [100, 400]
    assert programs.quality[programs.tier == 0].mean() > programs.quality[programs.tier == 1].mean() + 1.5


# --- Validation (acceptance test 8) ---------------------------------------------------------------------------------


def test_generated_population_is_valid():
    validate_population(generate_population(SimulationParams(), seed=11), SimulationParams())


def test_mismatched_attribute_keys_are_rejected():
    population = generate_population(SimulationParams(), seed=12)
    other = _params(applicants={"attributes": [{"key": "step_1", "program_weight_prior": 1}]})
    with pytest.raises(PopulationError, match="parameters list step_1"):
        validate_population(population, other)


def test_broken_populations_are_rejected():
    population = generate_population(SimulationParams(), seed=13)
    a, p = population.applicants, population.programs
    broken = [
        dataclasses.replace(population, applicants=dataclasses.replace(a, strength=a.strength.astype(np.float32))),
        dataclasses.replace(population, programs=dataclasses.replace(p, capacity=np.zeros_like(p.capacity))),
        dataclasses.replace(population, applicants=dataclasses.replace(a, weights=a.weights * 2)),
        dataclasses.replace(population, applicants=dataclasses.replace(a, keys=("board_scores", "board_scores", "x"))),
        dataclasses.replace(population, applicants=dataclasses.replace(a, names=("same",) * a.size)),
        dataclasses.replace(population, programs=dataclasses.replace(p, tier=p.tier + 1)),
    ]
    nan_strength = a.strength.copy()
    nan_strength[0] = np.nan
    broken.append(dataclasses.replace(population, applicants=dataclasses.replace(a, strength=nan_strength)))
    for candidate in broken:
        with pytest.raises(PopulationError):
            validate_population(candidate)


def test_more_programs_than_positions_is_rejected_for_uploaded_applicants():
    params = _params(market={"n_applicants": 1000, "n_programs": 900})
    few = generate_applicants(params, seed=14, n_applicants=500)
    with pytest.raises(PopulationError, match="900 programs need at least 900 positions"):
        generate_population(params, seed=14, applicants=few)
