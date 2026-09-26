"""The stage state machine: done, stale with reasons, running, failed, blocked, planned (plan steps 2.4, 3.7)."""

import pytest

from nrmps.models import Stage
from nrmps.params import load_params
from nrmps.pipeline import get_pipeline, needs_run
from nrmps.runs import execute_run, run_now, start_run

from .conftest import SMALL_PARAMS

pytestmark = pytest.mark.django_db

STAGES = [stage.value for stage in Stage]


def _states(simulation) -> dict[str, tuple[str, str]]:
    return {stage.key: (stage.state, stage.reason) for stage in get_pipeline(simulation)}


def _save(simulation, **groups):
    simulation.set_params(load_params(SMALL_PARAMS | groups))
    simulation.save()


def _stale_from(simulation, first: str) -> dict[str, tuple[str, str]]:
    """Return the states after checking that the stages before `first` are done and the rest are stale."""
    states = _states(simulation)
    split = STAGES.index(first)
    assert [states[key][0] for key in STAGES[:split]] == ["done"] * split
    assert [states[key][0] for key in STAGES[split:]] == ["stale"] * (len(STAGES) - split)
    return states


def test_every_stage_is_listed_in_order_and_implemented(simulation):
    stages = get_pipeline(simulation)
    assert [stage.key for stage in stages] == STAGES
    assert all(stage.implemented for stage in stages)


def test_stages_the_engine_does_not_implement_are_planned(simulation, monkeypatch):
    monkeypatch.setattr("nrmps.pipeline.IMPLEMENTED_STAGES", (Stage.POPULATION, Stage.PRE_INTERVIEW))
    states = _states(simulation)
    assert {key for key, (state, _reason) in states.items() if state == "planned"} == set(STAGES[2:])
    assert states["match"] == ("planned", "Not implemented yet.")


def test_new_simulation_is_ready(simulation):
    states = _states(simulation)
    assert {state for state, _reason in states.values()} == {"ready"}
    assert needs_run(get_pipeline(simulation))


def test_after_a_run_everything_is_done(finished_run, simulation):
    states = _states(simulation)
    assert states["population"] == ("done", "Up to date (run 1).")
    assert {state for state, _reason in states.values()} == {"done"}
    assert not needs_run(get_pipeline(simulation))


def test_changing_noise_keeps_the_population_and_makes_the_later_stages_stale(finished_run, simulation):
    _save(simulation, info={"program_pre_noise_sd": 0.9})
    states = _stale_from(simulation, "pre_interview")
    assert states["pre_interview"][1] == "Changed since run 1: information (noise)."
    assert states["applications"][1] == "Changed since run 1: the pre-interview views."
    assert states["match"][1] == "Changed since run 1: the rank order lists."


def test_changing_the_market_makes_every_stage_stale(finished_run, simulation):
    _save(simulation, market={"n_applicants": 70, "applicants_per_position": 1.2, "n_programs": 8})
    states = _stale_from(simulation, "population")
    assert states["population"][1] == "Changed since run 1: market."
    assert states["pre_interview"][1] == "Changed since run 1: the population."


def test_changing_the_seed_makes_every_stage_stale(finished_run, simulation):
    _save(simulation, run={"seed": 999})
    states = _stale_from(simulation, "population")
    assert states["population"][1] == "Changed since run 1: the seed."
    assert "the seed" in states["pre_interview"][1]


@pytest.mark.parametrize(
    ("groups", "first", "reason"),
    [
        ({"apps": {"mean": 5}}, "applications", "applications"),
        ({"signals": {"allocation": "random"}}, "signals", "signals"),
        ({"interview": {"applicant_cap": 3}}, "invitations", "the interview cap"),
        ({"info": {"fit_shock_sd": 0.9}}, "interviews", "the fit shock"),
        ({"rol": {"program_policy": "all_interviewed"}}, "rank_lists", "rank order lists"),
        ({"match": {"algorithm": "program_proposing"}}, "match", "the match settings"),
    ],
)
def test_a_stage_parameter_makes_that_stage_and_the_later_ones_stale(finished_run, simulation, groups, first, reason):
    _save(simulation, **groups)
    states = _stale_from(simulation, first)
    assert states[first][1] == f"Changed since run 1: {reason}."


def test_planned_parameters_do_not_make_anything_stale(finished_run, simulation):
    _save(simulation, run={"seed": 12345, "replicates": 5}, interview={"n_dates": 4})
    assert {state for state, _reason in _states(simulation).values()} == {"done"}


def test_a_blank_seed_matches_the_last_runs_seed(finished_run, simulation):
    _save(simulation, run={"seed": None})
    assert _states(simulation)["population"][0] == "done"


def test_a_queued_run_shows_on_every_implemented_stage(simulation, user):
    run = start_run(simulation, user)
    states = _states(simulation)
    assert states["population"] == ("queued", "Run 1 is queued.")
    assert {state for state, _reason in states.values()} == {"queued"}
    execute_run(run.pk)
    assert {state for state, _reason in _states(simulation).values()} == {"done"}


def test_a_failed_run_marks_the_stage_that_failed(simulation, user, monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("The market has no positions.")

    monkeypatch.setattr("nrmps.runs.run_pipeline", boom)
    run_now(simulation, user)
    states = _states(simulation)
    assert states["population"][0] == "ready"  # no successful run yet
    assert states["pre_interview"] == ("failed", "Run 1 failed: The market has no positions.")


def test_a_failure_in_a_later_stage_lands_on_that_stage(simulation, user, monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("No interviews to rank.")

    monkeypatch.setattr("nrmps.engine.pipeline.rank_lists", boom)
    run = run_now(simulation, user)
    recorded = dict(run.stages.values_list("stage", "status"))
    assert [recorded[key] for key in STAGES[:6]] == ["succeeded"] * 6
    assert recorded["rank_lists"] == "failed"
    assert "match" not in recorded
    states = _states(simulation)
    assert states["rank_lists"] == ("failed", "Run 1 failed: No interviews to rank.")
    assert states["interviews"][0] == "ready"


def test_invalid_saved_parameters_block_the_pipeline(simulation):
    simulation.params = {"schema_version": 1, "market": {"n_applicants": -1}}
    simulation.save()
    assert _states(simulation)["population"][0] == "blocked"
