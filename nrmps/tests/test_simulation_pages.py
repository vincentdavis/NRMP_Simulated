"""The simulation page, runs started from it and the run pages (plan steps 2.3 and 2.4)."""

import json

import pytest
from django.urls import reverse

from nrmps.models import Simulation, SimulationRun
from nrmps.params import SimulationParams, load_params
from nrmps.params_forms import post_data

from .conftest import SMALL_PARAMS

pytestmark = pytest.mark.django_db


def _manage(sim) -> str:
    return reverse("nrmps:simulation_manage", kwargs={"pk": sim.pk})


def _run_url(run, view: str = "run_detail", **extra) -> str:
    return reverse(f"nrmps:{view}", kwargs={"pk": run.simulation_id, "number": run.number, **extra})


def _body(response) -> str:
    return (b"".join(response.streaming_content) if response.streaming else response.content).decode()


def _toast(response) -> dict:
    return json.loads(response.headers["HX-Trigger"])["toast"]


def _params_post(params: SimulationParams, **changes) -> dict:
    return post_data(params) | {"form_id": "params"} | changes


# --- New simulations and parameters ----------------------------------------------------------------------------------


def test_new_simulation_starts_with_valid_defaults_and_its_own_seed(auth_client, user):
    response = auth_client.post(reverse("nrmps:simulation_create"), {"name": "First"})
    sim = Simulation.objects.get(name="First")
    assert response["Location"] == _manage(sim)
    params = sim.get_params()
    assert params.run.seed is not None
    assert params.with_seed(None) == SimulationParams()
    other = Simulation.objects.create(owner=user, name="Second")
    assert other.get_params().run.seed != params.run.seed


def test_untouched_parameter_form_saves(auth_client, simulation):
    response = auth_client.post(_manage(simulation), _params_post(simulation.get_params()))
    assert response.status_code == 302
    assert response["Location"].endswith("#run")


def test_saving_parameters_changes_only_the_draft(auth_client, simulation):
    data = _params_post(simulation.get_params(), prefs__applicant_pref_correlation="0.25")
    auth_client.post(_manage(simulation), data)
    simulation.refresh_from_db()
    assert simulation.get_params().prefs.applicant_pref_correlation == 0.25
    assert not SimulationRun.objects.exists()


def test_invalid_parameters_are_shown_and_not_saved(auth_client, simulation):
    data = _params_post(simulation.get_params(), **{"applicants__groups-0-share": "0.9"})
    response = auth_client.post(_manage(simulation), data)
    body = response.content.decode()
    assert response.status_code == 200
    assert "The parameters were not saved" in body
    assert "The group shares add up to" in body
    simulation.refresh_from_db()
    assert simulation.get_params() == load_params(SMALL_PARAMS)


def test_markets_above_the_size_limit_are_rejected(auth_client, simulation, settings):
    settings.NRMP_MAX_PAIRS = 400
    response = auth_client.post(_manage(simulation), _params_post(simulation.get_params()))
    assert "480 pairs, which is above the current limit of 400 pairs" in response.content.decode()


def test_save_and_run_goes_to_the_new_run(auth_client, simulation):
    response = auth_client.post(_manage(simulation), _params_post(simulation.get_params(), run="1"))
    run = simulation.runs.get()
    assert run.status == SimulationRun.Status.SUCCEEDED
    assert response["Location"] == _run_url(run)


def test_page_shows_the_pipeline_and_warnings(auth_client, simulation):
    data = load_params(SMALL_PARAMS | {"market": {"n_applicants": 60, "applicants_per_position": 2.5, "n_programs": 8}})
    simulation.set_params(data)
    simulation.save()
    body = auth_client.get(_manage(simulation)).content.decode()
    assert 'id="pipeline"' in body
    assert "Rank order lists" in body
    assert "2.5 applicants per position is unusual" in body


# --- Runs from the page -----------------------------------------------------------------------------------------------


def test_run_button_returns_the_panel_and_stepper_with_a_toast(auth_client, simulation):
    response = auth_client.post(
        reverse("nrmps:run_start", kwargs={"pk": simulation.pk}), headers={"hx-request": "true"}
    )
    assert _toast(response) == {"level": "success", "text": "Run 1 finished."}
    body = response.content.decode()
    assert body.lstrip().startswith('<section id="run-panel"')
    assert 'id="pipeline" class="mb-4" hx-swap-oob="outerHTML"' in body
    assert "Run again" in body


def test_run_errors_are_shown_in_the_panel(auth_client, simulation, settings):
    settings.NRMP_MAX_PAIRS = 10
    response = auth_client.post(
        reverse("nrmps:run_start", kwargs={"pk": simulation.pk}), headers={"hx-request": "true"}
    )
    assert _toast(response)["level"] == "error"
    assert "above the current limit of 10 pairs" in response.content.decode()


def test_run_without_javascript_redirects_to_the_run(auth_client, simulation):
    response = auth_client.post(reverse("nrmps:run_start", kwargs={"pk": simulation.pk}))
    assert response["Location"] == _run_url(simulation.runs.get())


def test_other_users_cannot_see_or_run_the_simulation(client, other_user, simulation, finished_run):
    client.force_login(other_user)
    assert client.get(_manage(simulation)).status_code == 404
    assert client.post(reverse("nrmps:run_start", kwargs={"pk": simulation.pk})).status_code == 404
    assert client.get(_run_url(finished_run)).status_code == 404
    assert client.get(_run_url(finished_run, "run_download", name="applicants.csv")).status_code == 404
    assert client.post(_run_url(finished_run, "run_delete")).status_code == 404


# --- Run pages --------------------------------------------------------------------------------------------------------


def test_run_page_shows_versions_stages_and_diagnostics(auth_client, finished_run):
    body = auth_client.get(_run_url(finished_run)).content.decode()
    for text in ("Run 1", "Model 2.0, engine 2.0.0", "Population", "Pre-interview", "Agreement (true utilities)"):
        assert text in body, text
    assert "Applicant groups" in body
    assert "Distributions" in body


@pytest.mark.parametrize("name", ["run_applicants", "run_programs"])
@pytest.mark.parametrize("sort", ["index", "name", "strength", "quality", "fidelity", "popularity", "bogus"])
def test_agent_lists_sort_and_paginate(auth_client, finished_run, name, sort):
    response = auth_client.get(_run_url(finished_run, name), {"sort": sort, "order": "desc", "page_size": 25})
    assert response.status_code == 200
    body = response.content.decode()
    assert "Showing 1\u2013" in body


@pytest.mark.parametrize(("requested", "used"), [("100000000", 100), ("-5", 100), ("abc", 100), ("25", 25)])
def test_page_size_is_limited_to_the_offered_sizes(auth_client, finished_run, requested, used):
    response = auth_client.get(_run_url(finished_run, "run_applicants"), {"page_size": requested})
    assert response.context["page_size"] == used


def test_applicant_list_shows_rounded_numbers_and_chips(auth_client, finished_run):
    body = auth_client.get(_run_url(finished_run, "run_applicants")).content.decode()
    assert "board_scores" in body
    assert "badge badge-outline badge-sm" in body
    assert "{&#x27;" not in body  # no Python dict reprs


@pytest.mark.parametrize(("name", "last"), [("run_applicant", 60), ("run_program", 8)])
def test_agent_pages_show_both_sides(auth_client, finished_run, name, last):
    response = auth_client.get(_run_url(finished_run, name, index=1))
    assert response.status_code == 200
    assert response.context["has_their_ranks"]
    assert auth_client.get(_run_url(finished_run, name, index=last)).status_code == 200
    assert auth_client.get(_run_url(finished_run, name, index=last + 1)).status_code == 404
    assert auth_client.get(_run_url(finished_run, name, index=0)).status_code == 404


def test_agent_pages_leave_out_the_other_sides_ranks_for_large_markets(auth_client, finished_run, settings):
    settings.NRMP_DRILLDOWN_MAX_PAIRS = 100
    response = auth_client.get(_run_url(finished_run, "run_applicant", index=1))
    assert not response.context["has_their_ranks"]
    assert "too large to recompute them" in response.content.decode()
    assert auth_client.get(_run_url(finished_run, "run_download", name="pairs.csv")).status_code == 404


def test_run_pages_of_a_failed_run(auth_client, simulation, user, monkeypatch):
    from nrmps.runs import run_now

    monkeypatch.setattr("nrmps.runs.run_pre_interview", lambda *a, **k: (_ for _ in ()).throw(ValueError("No luck.")))
    run = run_now(simulation, user)
    body = auth_client.get(_run_url(run)).content.decode()
    assert "This run failed: No luck." in body
    assert auth_client.get(_run_url(run, "run_applicants")).status_code == 404


# --- Downloads --------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "first_line", "lines"),
    [
        ("applicants.csv", "name,group,strength,board_scores,research,honors,weight:reputation", 61),
        ("programs.csv", "name,tier,quality,capacity,reputation,location,weight:board_scores", 9),
        ("pairs.csv", "applicant,program,applicant_true_utility,applicant_pre_interview_score", 481),
    ],
)
def test_csv_downloads_stream(auth_client, finished_run, name, first_line, lines):
    response = auth_client.get(_run_url(finished_run, "run_download", name=name))
    assert response.streaming
    assert response["Content-Disposition"] == f'attachment; filename="test-simulation-run-1-{name}"'
    body = _body(response)
    assert body.startswith(first_line)
    assert len(body.splitlines()) == lines


def test_json_downloads(auth_client, finished_run):
    record = json.loads(_body(auth_client.get(_run_url(finished_run, "run_download", name="metrics.json"))))
    assert record["seed"] == 12345
    assert record["stamps"]["model_version"] == "2.0"
    assert record["metrics"]["market"]["n_applicants"] == 60
    params = json.loads(_body(auth_client.get(_run_url(finished_run, "run_download", name="params.json"))))
    assert load_params(params) == load_params(SMALL_PARAMS)
    assert auth_client.get(_run_url(finished_run, "run_download", name="other.txt")).status_code == 404


def test_deleting_a_run(auth_client, finished_run, simulation):
    response = auth_client.post(_run_url(finished_run, "run_delete"), follow=True)
    assert "Deleted run 1." in response.content.decode()
    assert not simulation.runs.exists()
