"""Runs: frozen parameters, seeds, versions, artifacts, stages and reproducibility (plan step 2.3)."""

import numpy as np
import pytest

from nrmps.engine import ENGINE_VERSION, MODEL_VERSION
from nrmps.engine.persistence import population_digest, population_from_npz
from nrmps.engine.pipeline import run_pre_interview
from nrmps.exceptions import SimulationError, SizeLimitError
from nrmps.models import RunArtifact, SimulationRun, Stage
from nrmps.params import load_params
from nrmps.runs import RunData, RunInProgressError, execute_run, run_now, start_run

from .conftest import SMALL_PARAMS

pytestmark = pytest.mark.django_db


def _set_params(simulation, **groups):
    simulation.set_params(load_params(SMALL_PARAMS | groups))
    simulation.save()


def test_a_run_freezes_parameters_seed_and_versions(finished_run, simulation):
    run = finished_run
    assert run.number == 1
    assert run.status == SimulationRun.Status.SUCCEEDED
    assert run.seed == 12345
    assert not run.seed_was_drawn
    assert run.params == load_params(SMALL_PARAMS).to_json_data()
    assert run.params_hash == load_params(SMALL_PARAMS).params_hash()
    assert (run.model_version, run.engine_version, run.schema_version) == (MODEL_VERSION, ENGINE_VERSION, 1)
    assert run.numpy_version == np.__version__
    assert (run.n_applicants, run.n_programs, run.n_positions) == (60, 8, 50)
    assert run.population_source == {"applicants": "generated", "programs": "generated"}
    assert set(run.fingerprints) == {stage.value for stage in Stage}  # PostgreSQL does not keep the key order
    assert run.progress_done == run.progress_total == 2 * 480
    assert run.duration_ms is not None
    assert run.metrics["market"]["n_positions"] == 50


def test_a_run_stores_its_population_and_results(finished_run):
    kinds = set(finished_run.artifacts.values_list("kind", flat=True))
    assert kinds == {RunArtifact.Kind.POPULATION, RunArtifact.Kind.PRE_INTERVIEW, RunArtifact.Kind.STAGES}
    stages = {stage.stage: stage for stage in finished_run.stages.all()}
    assert set(stages) == set(Stage)
    assert {stage.status for stage in stages.values()} == {SimulationRun.Status.SUCCEEDED}
    assert all(stage.fingerprint == finished_run.fingerprints[key] for key, stage in stages.items())
    assert stages[Stage.POPULATION].counts == {"applicants": 60, "programs": 8, "positions": 50}
    assert stages[Stage.MATCH].counts["matched"] == finished_run.metrics["outcomes"]["match"]["matched"]
    assert stages[Stage.MATCH].counts["blocking_pairs"] == 0
    population = population_from_npz(finished_run.artifact(RunArtifact.Kind.POPULATION))
    assert population_digest(population) == finished_run.population_digest


def test_runs_repeat_exactly_and_match_the_engine(finished_run, simulation, user):
    again = run_now(simulation, user)
    assert again.number == 2
    assert again.population_digest == finished_run.population_digest
    assert again.metrics == finished_run.metrics
    assert again.fingerprints == finished_run.fingerprints
    direct = run_pre_interview(load_params(SMALL_PARAMS), 12345)
    assert population_digest(direct.population) == finished_run.population_digest


def test_blank_seed_draws_a_new_seed_per_run(simulation, user):
    _set_params(simulation, run={"seed": None})
    first, second = run_now(simulation, user), run_now(simulation, user)
    assert first.seed_was_drawn
    assert second.seed_was_drawn
    assert first.seed != second.seed
    assert first.params["run"]["seed"] == first.seed
    assert first.population_digest != second.population_digest


def test_changing_noise_keeps_the_population(finished_run, simulation, user):
    _set_params(simulation, info={"applicant_pre_noise_sd": 1.5})
    noisier = run_now(simulation, user)
    assert noisier.population_digest == finished_run.population_digest
    assert noisier.fingerprints["population"] == finished_run.fingerprints["population"]
    assert noisier.fingerprints["pre_interview"] != finished_run.fingerprints["pre_interview"]
    same_truth = finished_run.metrics["applicants"]["consensus"]["true_utility_correlation"]
    assert noisier.metrics["applicants"]["consensus"]["true_utility_correlation"] == same_truth


def test_only_one_active_run_per_simulation(simulation, user):
    queued = start_run(simulation, user)
    assert queued.status == SimulationRun.Status.QUEUED
    with pytest.raises(RunInProgressError):
        start_run(simulation, user)
    execute_run(queued.pk)
    assert start_run(simulation, user).number == 2


def test_execute_leaves_finished_runs_alone(finished_run):
    before = finished_run.metrics
    assert execute_run(finished_run.pk).metrics == before
    assert finished_run.stages.count() == len(Stage)


def test_market_above_the_limit_is_refused(simulation, user, settings):
    settings.NRMP_MAX_PAIRS = 100
    with pytest.raises(SizeLimitError, match="above the current limit of 100 pairs"):
        start_run(simulation, user)
    assert not SimulationRun.objects.exists()


def test_invalid_saved_parameters_are_reported(simulation, user):
    simulation.params = {"schema_version": 1, "market": {"n_applicants": -5}}
    simulation.save()
    with pytest.raises(SimulationError, match="saved parameters are not valid"):
        start_run(simulation, user)


def test_a_failure_during_execution_is_recorded(simulation, user, monkeypatch):
    run = start_run(simulation, user)

    def boom(*args, **kwargs):
        raise RuntimeError("engine bug")

    monkeypatch.setattr("nrmps.runs.run_pipeline", boom)
    run = execute_run(run.pk)
    assert run.status == SimulationRun.Status.FAILED
    assert "failed unexpectedly" in run.error
    assert "engine bug" not in run.error
    failed = run.stages.get(stage=Stage.PRE_INTERVIEW)
    assert failed.status == SimulationRun.Status.FAILED
    assert start_run(simulation, user).number == 2  # a failed run is not active


def test_run_data_recomputes_one_agents_rows(finished_run):
    data = RunData(finished_run)
    rows = data.applicant_rows(4)
    assert rows.true.shape == (8,)
    assert sorted(rows.observed_rank.tolist()) == list(range(1, 9))
    assert data.applicant_results is not None
    assert data.applicant_results.first_choice[4] == int(np.argmin(rows.observed_rank))
    program_rows = data.program_rows(2)
    # The program's true utility for applicant 4 equals what applicant 4's page shows as the program's view.
    assert program_rows.true[4] == rows.other_true[2]
    assert rows.other_observed_rank is not None
    assert program_rows.observed_rank[4] == rows.other_observed_rank[2]


def test_pairs_cover_every_pair_once(finished_run):
    rows = list(RunData(finished_run).pair_rows())
    assert len(rows) == 480
    assert len({(row[0], row[1]) for row in rows}) == 480


def test_seed_demo_creates_a_user_a_simulation_and_a_run(monkeypatch):
    import io

    from django.core.management import call_command

    from nrmps.models import Simulation, User

    monkeypatch.setenv("NRMP_DEMO_PASSWORD", "Demo-Password-123")
    out = io.StringIO()
    call_command("seed_demo", "--username", "demo", stdout=out)
    user = User.objects.get(username="demo")
    assert user.check_password("Demo-Password-123")
    simulation = Simulation.objects.get(owner=user)
    run = simulation.runs.get()
    assert run.status == SimulationRun.Status.SUCCEEDED
    assert run.seed == 2026
    assert "Created “Demo market”" in out.getvalue()
    call_command("seed_demo", "--username", "demo", "--name", "Second", stdout=io.StringIO())
    assert Simulation.objects.filter(owner=user).count() == 2
