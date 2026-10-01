"""The idealized market (preset "idealized"): one measure on each side, seen exactly at every stage."""

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
