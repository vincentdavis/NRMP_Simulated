"""The stage state machine: done, stale with reasons, running, failed, blocked, planned (plan step 2.4)."""

import pytest

from nrmps.models import Stage
from nrmps.params import load_params
from nrmps.pipeline import get_pipeline, needs_run
from nrmps.runs import execute_run, run_now, start_run

from .conftest import SMALL_PARAMS

pytestmark = pytest.mark.django_db

PLANNED = {"applications", "signals", "invitations", "interviews", "rank_lists", "match"}


def _states(simulation) -> dict[str, tuple[str, str]]:
    return {stage.key: (stage.state, stage.reason) for stage in get_pipeline(simulation)}


def _save(simulation, **groups):
    simulation.set_params(load_params(SMALL_PARAMS | groups))
    simulation.save()


def test_every_stage_is_listed_in_order_and_later_ones_are_planned(simulation):
    stages = get_pipeline(simulation)
    assert [stage.key for stage in stages] == [stage.value for stage in Stage]
    assert {stage.key for stage in stages if stage.state == "planned"} == PLANNED


def test_new_simulation_is_ready(simulation):
    states = _states(simulation)
    assert states["population"][0] == "ready"
    assert states["pre_interview"][0] == "ready"
    assert needs_run(get_pipeline(simulation))


def test_after_a_run_everything_is_done(finished_run, simulation):
    states = _states(simulation)
    assert states["population"] == ("done", "Up to date (run 1).")
    assert states["pre_interview"][0] == "done"
    assert not needs_run(get_pipeline(simulation))


def test_changing_noise_makes_only_the_pre_interview_stage_stale(finished_run, simulation):
    _save(simulation, info={"program_pre_noise_sd": 0.9})
    states = _states(simulation)
    assert states["population"][0] == "done"
    assert states["pre_interview"] == ("stale", "Changed since run 1: information (noise).")


def test_changing_the_market_makes_both_stages_stale(finished_run, simulation):
    _save(simulation, market={"n_applicants": 70, "applicants_per_position": 1.2, "n_programs": 8})
    states = _states(simulation)
    assert states["population"] == ("stale", "Changed since run 1: market.")
    assert states["pre_interview"] == ("stale", "Changed since run 1: the population.")


def test_changing_the_seed_makes_both_stages_stale(finished_run, simulation):
    _save(simulation, run={"seed": 999})
    states = _states(simulation)
    assert states["population"] == ("stale", "Changed since run 1: the seed.")
    assert "the seed" in states["pre_interview"][1]


def test_planned_parameters_do_not_make_anything_stale(finished_run, simulation):
    _save(simulation, apps={"mean": 12}, run={"seed": 12345, "replicates": 5})
    states = _states(simulation)
    assert states["population"][0] == "done"
    assert states["pre_interview"][0] == "done"


def test_a_blank_seed_matches_the_last_runs_seed(finished_run, simulation):
    _save(simulation, run={"seed": None})
    assert _states(simulation)["population"][0] == "done"


def test_a_queued_run_shows_on_every_implemented_stage(simulation, user):
    run = start_run(simulation, user)
    states = _states(simulation)
    assert states["population"] == ("queued", "Run 1 is queued.")
    assert states["pre_interview"][0] == "queued"
    execute_run(run.pk)
    assert _states(simulation)["pre_interview"][0] == "done"


def test_a_failed_run_marks_the_stage_that_failed(simulation, user, monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("The market has no positions.")

    monkeypatch.setattr("nrmps.runs.run_pre_interview", boom)
    run_now(simulation, user)
    states = _states(simulation)
    assert states["population"][0] == "ready"  # no successful run yet
    assert states["pre_interview"] == ("failed", "Run 1 failed: The market has no positions.")


def test_invalid_saved_parameters_block_the_pipeline(simulation):
    simulation.params = {"schema_version": 1, "market": {"n_applicants": -1}}
    simulation.save()
    assert _states(simulation)["population"][0] == "blocked"
