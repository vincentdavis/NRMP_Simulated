"""The markets with one measure on each side: the idealized one, seen exactly, and the noisy one, seen through the
largest noise the parameters allow (presets "idealized" and "noisy")."""

import math

import numpy as np
import pytest
from scipy.stats import spearmanr

from nrmps.engine.pipeline import run_pipeline
from nrmps.params import SimulationParams, load_params
from nrmps.presets import PRESETS, _merge, preset_params

# Without the limits: every applicant applies everywhere, and every program can interview every applicant.
NO_LIMITS = {
    "market": {"n_applicants": 60, "applicants_per_position": 1.2, "n_programs": 8},
    "apps": {"strategy": "all"},
    "invites": {"interviews_per_position": 30, "rounds": 1},
    "interview": {"applicant_cap": 50},
}


def _strength_quality(result):
    population = result.population
    return np.asarray(population.applicants.strength), np.asarray(population.programs.quality)


def test_every_list_follows_true_quality():
    """Applicants rank programs by quality alone and programs rank applicants by strength alone, as seen exactly;
    everyone sends the same number of applications, and the match is stable."""
    result = run_pipeline(preset_params("idealized", seed=2026), 2026)
    strength, quality = _strength_quality(result)
    apps, lists = result.applications, result.lists
    assert (np.asarray(apps.count) == 30).all()
    for owner, rank, value in (
        (apps.i, lists.applicant_rank, quality[apps.j]),
        (apps.j, lists.program_rank, strength[apps.i]),
    ):
        on = rank > 0
        order = np.lexsort((rank[on], owner[on]))  # each list, from its first choice down
        same_list = owner[on][order][1:] == owner[on][order][:-1]
        assert (np.diff(value[on][order])[same_list] <= 0).all()
    assert result.match.blocking_pairs == 0


@pytest.mark.parametrize("seed", [2026, 7, 11])
def test_without_the_limits_the_match_sorts_perfectly(seed):
    """With every application made and every interview possible, the only stable match is perfect sorting: the
    strongest applicants fill the positions, and no stronger applicant is at a worse program."""
    data = _merge(_merge(SimulationParams().to_json_data(), PRESETS["idealized"].changes), NO_LIMITS)
    data["run"] = dict(data["run"]) | {"seed": seed}
    result = run_pipeline(load_params(data), seed)
    strength, quality = _strength_quality(result)
    program = np.asarray(result.match.program)
    positions = int(np.asarray(result.population.programs.capacity).sum())
    strongest = np.zeros(strength.size, dtype=bool)
    strongest[np.argsort(-strength)[:positions]] = True
    assert np.array_equal(program >= 0, strongest)
    matched = np.flatnonzero(program >= 0)
    by_strength = matched[np.argsort(-strength[matched])]
    assert (np.diff(quality[program[by_strength]]) <= 0).all()


def test_it_sorts_better_than_the_nrmp_like_market():
    """With the same limits, taking away taste and noise sorts the strongest applicants into the best programs far more
    closely (about 0.94 against 0.72 at this seed)."""
    correlation = {}
    for key in ("idealized", "nrmp_like"):
        result = run_pipeline(preset_params(key, seed=2026), 2026)
        strength, quality = _strength_quality(result)
        program = np.asarray(result.match.program)
        matched = program >= 0
        correlation[key] = spearmanr(strength[matched], quality[program[matched]]).statistic
    assert correlation["idealized"] > 0.9
    assert correlation["idealized"] > correlation["nrmp_like"] + 0.1


def _flat(data, prefix=""):
    """Return {"group.field": value} for nested parameter data."""
    flat = {}
    for key, value in data.items():
        if isinstance(value, dict):
            flat |= _flat(value, f"{prefix}{key}.")
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def test_the_noisy_market_differs_from_the_idealized_one_only_in_its_noise():
    idealized = _flat(preset_params("idealized", seed=1).to_json_data())
    noisy = _flat(preset_params("noisy", seed=1).to_json_data())
    changed = {key: (idealized[key], noisy[key]) for key in idealized if idealized[key] != noisy[key]}
    assert changed == {
        "info.applicant_pre_noise_sd": (0.0, 3.0),
        "info.program_pre_noise_sd": (0.0, 3.0),
        "info.interview_informativeness": (1.0, 0.0),
        "apps.self_assessment_noise_sd": (0.0, 2.0),
    }


def test_the_noisy_market_is_as_noisy_as_set_and_interviews_correct_none_of_it():
    """Each view is the true value plus an error three times its spread, so each agent's ranking agrees with the
    true one only as much as theory says (Spearman 6/pi * asin(rho/2) with rho = 1/sqrt(10), about 0.30); the
    interview leaves every view as it was."""
    result = run_pipeline(preset_params("noisy", seed=2026), 2026)
    expected = 6 / math.pi * math.asin(1 / math.sqrt(10) / 2)
    for side in (result.pre.applicants, result.pre.programs):
        assert abs(float(np.nanmean(side.fidelity)) - expected) < 0.03
    interviewed = np.asarray(result.invitations.accepted).astype(bool)
    assert interviewed.sum() > 1000
    np.testing.assert_allclose(
        np.asarray(result.interviews.applicant_post)[interviewed], np.asarray(result.applications.observed)[interviewed]
    )


def test_noise_scrambles_the_sorting_but_the_match_stays_stable():
    """Against the idealized market at the same seed: the match is stable on the lists people made, but strength
    and the matched program's quality barely go together (about 0.26 against 0.94)."""
    correlation = {}
    for key in ("idealized", "noisy"):
        result = run_pipeline(preset_params(key, seed=2026), 2026)
        strength, quality = _strength_quality(result)
        program = np.asarray(result.match.program)
        matched = program >= 0
        correlation[key] = spearmanr(strength[matched], quality[program[matched]]).statistic
        assert result.match.blocking_pairs == 0
    assert correlation["noisy"] < 0.5
    assert correlation["idealized"] > correlation["noisy"] + 0.4
