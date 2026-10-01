"""The simulation page, runs started from it and the run pages (plan steps 2.3, 2.4 and 3.7)."""

import csv
import io
import json

import numpy as np
import pytest
from django.urls import reverse

from nrmps.engine import ENGINE_VERSION, MODEL_VERSION
from nrmps.engine.pipeline import run_pipeline
from nrmps.models import RunArtifact, Simulation, SimulationRun
from nrmps.params import SimulationParams, load_params
from nrmps.params_forms import post_data
from nrmps.runs import RunData

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


def test_run_summary_shows_versions_stages_and_checks(auth_client, finished_run):
    body = auth_client.get(_run_url(finished_run)).content.decode()
    for text in (
        "Run 1",
        f"Model {MODEL_VERSION}, engine {ENGINE_VERSION}",
        "Population",
        "Pre-interview",
        "applicant list entries",  # stage counts in words
        "Checks passed",
        "How this match was checked",
        "The match: every applicant's result (CSV)",
        "Parameters of this run",
    ):
        assert text in body, text


RUN_TABS = ["run_detail", "run_population", "run_pre_interview", "run_applications", "run_match", "run_applicants"]
RUN_TABS += ["run_programs"]


@pytest.mark.parametrize("view", RUN_TABS)
def test_every_run_tab_links_to_the_others(auth_client, finished_run, view):
    response = auth_client.get(_run_url(finished_run, view))
    assert response.status_code == 200
    body = response.content.decode()
    for other in RUN_TABS:
        assert f'href="{_run_url(finished_run, other)}"' in body, other
    # The current page is the active tab, in the primary colour, and says so to screen readers.
    active = 'tab-active [--tab-bg:color-mix(in_oklab,var(--color-primary)_80%,black)] text-primary-content"'
    assert f'{active} href="{_run_url(finished_run, view)}" aria-current="page"' in body


def test_the_population_tab_compares_the_market_with_the_request(auth_client, finished_run):
    body = auth_client.get(_run_url(finished_run, "run_population")).content.decode()
    for text in (
        "Applicant groups",
        "Program tiers",
        "Distributions",
        "Did the generator produce",
        "applicants per position",
    ):
        assert text in body, text


def test_the_pre_interview_tab_shows_agreement_and_fidelity(auth_client, finished_run):
    body = auth_client.get(_run_url(finished_run, "run_pre_interview")).content.decode()
    for text in ("Agreement (true utilities)", "Applicant agreement", "How accurately do applicants see programs?"):
        assert text in body, text


def test_the_match_tab_shows_the_match_and_who_matched(auth_client, finished_run):
    body = auth_client.get(_run_url(finished_run, "run_match")).content.decode()
    match = finished_run.metrics["outcomes"]["match"]
    for text in (
        "The match",
        "Match rate",
        f"{match['match_rate'] * 100:.1f}%",
        f"{match['matched']} of {match['certified']} applicants with a rank order list",
        "Which choice did applicants match to?",
        "Who matched where",
        "Do stronger applicants match to better programs?",
        "How this match was checked",
        "Blocking pairs: an applicant and a program",
        "Who matched",
        "By strength decile",
        "Rank order lists",
    ):
        assert text in body, text
    assert "Passed" in body


def test_the_applications_tab_has_the_funnel_and_every_application(auth_client, finished_run):
    response = auth_client.get(_run_url(finished_run, "run_applications"), {"page_size": 500})
    body = response.content.decode()
    for text in ("From applications to rank order lists", "No signals were sent", "Every application", "Stage reached"):
        assert text in body, text
    record = RunData(finished_run).stages
    assert response.context["page_obj"].paginator.count == record.i.shape[0]
    matched = int((record.match_program[record.i] == record.j).sum())
    assert sum(row["matched"] for row in response.context["rows"]) == matched


@pytest.mark.parametrize(
    ("filters", "check"),
    [
        ({"status": "matched"}, lambda row: row["matched"]),
        ({"status": "interviewed"}, lambda row: row["interviewed"]),
        ({"status": "declined"}, lambda row: row["wave"] and not row["interviewed"]),
        ({"status": "not_invited"}, lambda row: not row["wave"]),
        ({"status": "ranked"}, lambda row: row["applicant_rank"]),
        ({"signal": "no"}, lambda row: not row["signal"]),
        ({"applicant": "applicant 7"}, lambda row: "applicant 7" in row["applicant_name"].lower()),
        ({"program": "PROGRAM 3"}, lambda row: row["program_name"] == "Program 3"),
    ],
)
def test_the_applications_can_be_filtered(auth_client, finished_run, filters, check):
    response = auth_client.get(_run_url(finished_run, "run_applications"), filters | {"page_size": 500})
    rows = response.context["rows"]
    assert rows
    assert all(check(row) for row in rows)
    assert response.context["filtered"]


def test_the_applications_sort_and_say_when_nothing_matches(auth_client, finished_run):
    url = _run_url(finished_run, "run_applications")
    ranks = [row["program_rank"] for row in auth_client.get(url, {"sort": "program_rank"}).context["rows"]]
    ranked = [rank for rank in ranks if rank is not None]
    assert ranked == sorted(ranked)
    assert ranks[: len(ranked)] == ranked  # unranked last
    assert auth_client.get(url, {"sort": "bogus", "status": "bogus"}).status_code == 200
    body = auth_client.get(url, {"applicant": "nobody at all"}).content.decode()
    assert "No application matches these filters." in body


def test_the_stepper_links_each_stage_to_its_results(auth_client, finished_run, simulation):
    body = auth_client.get(_manage(simulation)).content.decode()
    for view in ("run_population", "run_pre_interview", "run_applications", "run_match"):
        assert f'href="{_run_url(finished_run, view)}"' in body, view


@pytest.mark.parametrize("name", ["run_applicants", "run_programs"])
@pytest.mark.parametrize(
    "sort",
    [
        "index",
        "name",
        "strength",
        "quality",
        "fidelity",
        "popularity",
        "applications",
        "interviews",
        "match",
        "fill",
        "x",
    ],
)
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
    response = auth_client.get(_run_url(finished_run, "run_applicant", index=1), {"view": "pre"})
    assert not response.context["has_their_ranks"]
    assert "too large to recompute them" in response.content.decode()
    assert auth_client.get(_run_url(finished_run, "run_download", name="pairs.csv")).status_code == 404


def test_run_summaries_show_the_match_rate(auth_client, finished_run, simulation, user):
    from nrmps.runs import run_now

    run_now(simulation, user)
    body = auth_client.get(_manage(simulation)).content.decode()
    rate = f"{finished_run.metrics['outcomes']['match']['match_rate'] * 100:.1f}%"
    assert "Positions filled" in body
    assert body.count(rate) >= 3  # the latest run's summary and both rows of the recent runs


def test_lists_show_each_agents_stages_and_match(auth_client, finished_run):
    response = auth_client.get(_run_url(finished_run, "run_applicants"), {"sort": "match"})
    body = response.content.decode()
    assert "Matched to" in body
    assert "choice)" in body
    first = response.context["rows"][0]
    assert first["match_rank"] == 1
    assert first["applications"] >= first["interviews"]
    programs = auth_client.get(_run_url(finished_run, "run_programs"), {"sort": "fill"})
    rows = programs.context["rows"]
    assert all(row["filled"] <= row["capacity"] for row in rows)
    assert sum(row["filled"] for row in rows) == finished_run.metrics["outcomes"]["match"]["matched"]


def test_an_applicants_page_follows_them_through_the_stages(auth_client, finished_run):
    record = RunArtifact.objects.get(run=finished_run, kind=RunArtifact.Kind.STAGES)
    assert record.size > 0
    matched = next(row for row in _match_rows(auth_client, finished_run) if row["matched_program"])
    index = int(matched["applicant"].rsplit(" ", 1)[-1])
    response = auth_client.get(_run_url(finished_run, "run_applicant", index=index))
    body = response.content.decode()
    assert response.context["view"] == "stages"
    assert "In the match" in body
    assert 'Matched to <a class="link"' in body
    assert matched["matched_program"] in body
    rows = response.context["rows"]
    assert len(rows) == int(matched["applications"])
    assert [row["list_rank"] for row in rows[: int(matched["list_length"])]] == list(
        range(1, int(matched["list_length"]) + 1)
    )
    assert sum(row["matched"] for row in rows) == 1
    assert sum(row["interviewed"] for row in rows) == int(matched["interviews"])
    pre = auth_client.get(_run_url(finished_run, "run_applicant", index=index), {"view": "pre"})
    assert pre.context["view"] == "pre"
    assert len(pre.context["rows"]) == finished_run.n_programs


def test_a_programs_page_lists_its_applicants_and_the_positions_filled(auth_client, finished_run):
    response = auth_client.get(_run_url(finished_run, "run_program", index=1), {"sort": "their_list_rank"})
    body = response.content.decode()
    journey = response.context["journey"]
    assert f"Filled {len(journey['matched'])} of {journey['positions']} position" in body
    assert "Applications received" in body
    assert "Signal received" in body
    assert len(response.context["rows"]) == min(journey["applied"], 100)


def _match_rows(auth_client, run) -> list[dict[str, str]]:
    body = _body(auth_client.get(_run_url(run, "run_download", name="match.csv")))
    return list(csv.DictReader(io.StringIO(body)))


def test_stage_downloads_agree_with_the_engine(auth_client, finished_run):
    result = run_pipeline(load_params(SMALL_PARAMS), 12345)
    body = _body(auth_client.get(_run_url(finished_run, "run_download", name="applications.csv")))
    rows = list(csv.DictReader(io.StringIO(body)))
    assert len(rows) == result.applications.size
    assert [float(row["applicant_pre_interview_view"]) for row in rows] == result.applications.observed.tolist()
    post = [float(row["applicant_post_interview_view"] or "nan") for row in rows]
    assert np.array_equal(post, result.interviews.applicant_post, equal_nan=True)
    program_post = [float(row["program_post_interview_view"] or "nan") for row in rows]
    assert np.array_equal(program_post, result.interviews.program_post, equal_nan=True)
    assert sum(int(row["matched"]) for row in rows) == int((result.match.program >= 0).sum())
    assert {row["interviewed"] for row in rows if row["applicant_list_rank"]} == {"1"}
    matches = _match_rows(auth_client, finished_run)
    assert len(matches) == 60
    assert sum(1 for row in matches if row["matched_program"]) == int((result.match.program >= 0).sum())
    assert {row["program_if_the_other_side_proposes"] for row in matches} == {""}  # compare_both is off
    programs = _body(auth_client.get(_run_url(finished_run, "run_download", name="program_results.csv")))
    program_rows = list(csv.DictReader(io.StringIO(programs)))
    assert [int(row["filled"]) for row in program_rows] == result.match.filled.tolist()


def test_runs_from_before_the_match_still_open(auth_client, finished_run):
    finished_run.artifacts.filter(kind=RunArtifact.Kind.STAGES).delete()
    metrics = dict(finished_run.metrics)
    del metrics["outcomes"]
    SimulationRun.objects.filter(pk=finished_run.pk).update(metrics=metrics)
    body = auth_client.get(_run_url(finished_run)).content.decode()
    assert "Checks passed" not in body
    assert f'href="{_run_url(finished_run, "run_pre_interview")}"' in body
    assert f'href="{_run_url(finished_run, "run_match")}"' not in body
    assert auth_client.get(_run_url(finished_run, "run_match")).status_code == 404
    assert auth_client.get(_run_url(finished_run, "run_applications")).status_code == 404
    assert auth_client.get(_run_url(finished_run, "run_pre_interview")).status_code == 200
    applicants = auth_client.get(_run_url(finished_run, "run_applicants"))
    assert not applicants.context["has_stages"]
    assert "sort=match" not in applicants.content.decode()  # no Matched to column
    page = auth_client.get(_run_url(finished_run, "run_applicant", index=1))
    assert page.context["view"] == "pre"
    assert "In the match" not in page.content.decode()
    assert auth_client.get(_run_url(finished_run, "run_download", name="match.csv")).status_code == 404


def test_run_pages_of_a_failed_run(auth_client, simulation, user, monkeypatch):
    from nrmps.runs import run_now

    monkeypatch.setattr("nrmps.runs.run_pipeline", lambda *a, **k: (_ for _ in ()).throw(ValueError("No luck.")))
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
    assert record["stamps"]["model_version"] == MODEL_VERSION
    assert record["metrics"]["market"]["n_applicants"] == 60
    params = json.loads(_body(auth_client.get(_run_url(finished_run, "run_download", name="params.json"))))
    assert load_params(params) == load_params(SMALL_PARAMS)
    assert auth_client.get(_run_url(finished_run, "run_download", name="other.txt")).status_code == 404


def test_deleting_a_run(auth_client, finished_run, simulation):
    response = auth_client.post(_run_url(finished_run, "run_delete"), follow=True)
    assert "Deleted run 1." in response.content.decode()
    assert not simulation.runs.exists()
