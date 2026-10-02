"""Comparing two runs: what they share, key numbers with differences, the parameters that differ, and the page."""

import json

import pytest
from django.urls import reverse
from django.utils.html import escape

from nrmps import help_registry
from nrmps.compare import (
    NUMBERS,
    comparison_charts,
    difference,
    key_numbers,
    pairing,
    parameter_differences,
    same_setup,
    shown,
)
from nrmps.models import Simulation, SimulationRun
from nrmps.params import load_params
from nrmps.run_views import run_key
from nrmps.runs import RunData, run_now

from .conftest import SMALL_PARAMS

pytestmark = pytest.mark.django_db

RERUN_FORM = 'action="/compare/same-seed/"'  # the form of "Run B again with A's seed" (the Help panel names it too)


def _changed(simulation, **changes):
    """Save the simulation's parameters with nested values replaced, each given as "section__name"=value."""
    data = simulation.get_params().to_json_data()
    for path, value in changes.items():
        section, name = path.split("__")
        data[section][name] = value
    simulation.set_params(load_params(data))
    simulation.save()
    return simulation


def _other_simulation(user, name="Another simulation", **params):
    return Simulation.objects.create(owner=user, name=name, params=load_params(SMALL_PARAMS | params).to_json_data())


def _url(a=None, b=None):
    keys = "&".join(f"{side}={run_key(run)}" for side, run in (("a", a), ("b", b)) if run is not None)
    return reverse("nrmps:compare") + (f"?{keys}" if keys else "")


@pytest.fixture
def noisier_run(simulation, user, finished_run):
    """Return a second run of the simulation with the same seed and noisier programs."""
    run = run_now(_changed(simulation, info__program_pre_noise_sd=2.5), user)
    assert run.status == "succeeded", run.error
    return run


@pytest.fixture
def other_seed_run(user):
    """Return a run of another simulation with the same parameters as the test simulation and another seed."""
    run = run_now(_other_simulation(user, run={"seed": 999}), user)
    assert run.status == "succeeded", run.error
    return run


# --- What the runs share ----------------------------------------------------------------------------------------------


def test_two_runs_of_the_same_parameters_and_seed_are_identical(simulation, user, finished_run):
    again = run_now(simulation, user)
    shared = pairing(finished_run, again)
    assert shared.identical
    assert shared.same_seed
    assert shared.same_population
    assert shared.differs_from == ""
    assert "their results are the same" in shared.note
    assert parameter_differences(finished_run, again) == []


def test_runs_with_the_same_seed_share_the_stages_before_the_parameter_that_differs(finished_run, noisier_run):
    """Program noise is read by the pre-interview stage: the population is shared, the rest is not."""
    shared = pairing(finished_run, noisier_run)
    assert not shared.identical
    assert shared.paired
    assert shared.same_seed
    assert shared.same_population
    assert shared.shared == ("Population",)
    assert shared.differs_from == "Pre-interview"
    assert "first differ at the Pre-interview stage" in shared.note
    assert "come from the parameters that differ" in shared.note


def test_a_parameter_of_a_later_stage_leaves_the_earlier_stages_shared(simulation, user, finished_run):
    later = run_now(_changed(simulation, match__compare_both=not simulation.get_params().match.compare_both), user)
    shared = pairing(finished_run, later)
    assert shared.differs_from == "Match"
    assert shared.shared[-1] == "Rank order lists"
    assert len(shared.shared) == 7


def test_runs_with_different_seeds_are_not_paired(finished_run, other_seed_run):
    shared = pairing(finished_run, other_seed_run)
    assert not shared.paired
    assert not shared.same_seed
    assert not shared.same_population
    assert shared.differs_from == "Population"
    assert "can be chance alone" in shared.note
    assert "give both the same seed" in shared.note


def test_the_same_seed_with_another_population_says_so(user, finished_run):
    bigger = run_now(
        _other_simulation(user, market={"n_applicants": 80, "applicants_per_position": 1.2, "n_programs": 8}), user
    )
    shared = pairing(finished_run, bigger)
    assert shared.same_seed
    assert not shared.same_population
    assert not shared.paired
    assert "the parameters that build the population differ" in shared.note


def test_a_run_can_be_repeated_while_its_simulation_keeps_its_parameters(simulation, finished_run):
    assert same_setup(finished_run)
    _changed(simulation, run__seed=777)  # another seed is still the same setup
    finished_run.refresh_from_db()
    assert same_setup(SimulationRun.objects.get(pk=finished_run.pk))
    _changed(simulation, info__program_pre_noise_sd=2.5)
    assert not same_setup(SimulationRun.objects.get(pk=finished_run.pk))


# --- Numbers ----------------------------------------------------------------------------------------------------------


def test_numbers_and_their_differences_as_text():
    assert shown(None, "share") == "-"
    assert shown(0.8066, "share") == "80.7%"
    assert shown(1234.0, "count") == "1,234"
    assert shown(0.96234, "three") == "0.962"
    assert difference(0.75, 0.8, "share") == "+5.0 pts"
    assert difference(0.8, 0.75, "share") == "-5.0 pts"
    assert difference(0.8, 0.8001, "share") == "0.0 pts"  # nothing after rounding: no sign
    assert difference(0.8, 0.7999, "share") == "0.0 pts"
    assert difference(1000, 1250, "count") == "+250"
    assert difference(60, 60, "count") == "0"
    assert difference(8.3, 8.1, "one") == "-0.2"
    assert difference(0.962, 0.514, "three") == "-0.448"
    assert difference(None, 0.5, "share") == "-"
    assert difference(0.5, None, "three") == "-"


def test_the_key_numbers_are_each_run_s_own(finished_run, noisier_run):
    groups = key_numbers(RunData(finished_run), RunData(noisier_run))
    assert [group["title"] for group in groups] == [title for title, _rows in NUMBERS]
    rows = {row["label"]: row for group in groups for row in group["rows"]}
    assert len(rows) == sum(len(group_rows) for _title, group_rows in NUMBERS)
    assert rows["Applicants"] == {"label": "Applicants", "a": "60", "b": "60", "difference": "0"}
    for run, side in ((finished_run, "a"), (noisier_run, "b")):
        match = run.metrics["outcomes"]["match"]
        assert rows["Match rate (applicants with a rank order list)"][side] == f"{match['match_rate'] * 100:.1f}%"
        assert rows["Applicants matched (of all applicants)"][side] == f"{match['matched'] / 60 * 100:.1f}%"
        assert rows["Positions filled"][side] == f"{match['fill_rate'] * 100:.1f}%"
        fidelity = run.metrics["programs"]["fidelity"]["pooled_correlation"]
        assert rows["Programs' fidelity"][side] == f"{fidelity:.3f}"
    # Noisier programs see applicants less well; the applicants' view is untouched.
    assert rows["Programs' fidelity"]["difference"].startswith("-")
    assert rows["Applicants' fidelity"]["difference"] == "0.000"
    assert rows["Sorting"]["a"] != "-"
    assert rows["Matched, top 20% of applicants by strength"]["a"].endswith("%")


# --- Parameters that differ -------------------------------------------------------------------------------------------


def test_only_the_parameters_that_differ_are_listed(finished_run, noisier_run):
    assert parameter_differences(finished_run, noisier_run) == [
        {"section": "Information", "title": "Program pre-interview noise", "a": "0.5", "b": "2.5"}
    ]


def test_the_seed_and_a_list_are_rows_too_in_the_form_s_order(user, finished_run):
    groups = [
        {"name": "strong", "share": 0.5, "strength_mean": 0.5},
        {"name": "weak", "share": 0.5, "strength_mean": -0.5},
    ]
    other = _other_simulation(user, run={"seed": 999}, applicants={"groups": groups})
    _changed(other, match__compare_both=not other.get_params().match.compare_both)
    rows = parameter_differences(finished_run, run_now(other, user))
    assert [row["title"] for row in rows] == ["Random seed", "Applicant groups", "Compare both sides proposing"]
    assert [row["section"] for row in rows] == ["Run", "Applicants", "Match"]
    assert (rows[0]["a"], rows[0]["b"]) == ("12345", "999")
    assert rows[1]["b"] == "2: strong, weak"
    assert rows[1]["a"].startswith(f"{len(finished_run.params['applicants']['groups'])}: ")


def test_a_list_with_the_same_names_and_other_values_says_so(user, finished_run):
    groups = finished_run.get_params().to_json_data()["applicants"]["groups"]
    groups[0]["strength_mean"] += 0.25
    rows = parameter_differences(finished_run, run_now(_other_simulation(user, applicants={"groups": groups}), user))
    assert [row["title"] for row in rows] == ["Applicant groups"]
    assert rows[0]["a"].endswith("(other values)")
    assert rows[0]["a"] == rows[0]["b"]


# --- Charts -----------------------------------------------------------------------------------------------------------


def test_the_comparison_s_charts_show_both_runs(finished_run, noisier_run):
    charts = comparison_charts(RunData(finished_run), RunData(noisier_run))
    assert set(charts) == {
        "compare_strength",
        "compare_choice",
        "compare_interviews",
        "compare_fill",
        "sorting_a",
        "sorting_b",
    }
    json.dumps({key: chart["payload"] for key, chart in charts.items()})  # plain JSON
    for key in ("compare_strength", "compare_choice", "compare_interviews", "compare_fill"):
        chart, payload = charts[key], charts[key]["payload"]
        assert [run["name"] for run in payload["runs"]] == ["A", "B"]
        assert chart["summary"]
        assert chart["head"]
        assert len(chart["rows"]) == len(payload["labels"]) == len(payload["names"])
        for run in payload["runs"]:
            assert len(run["values"]) == len(run["counts"]) == len(run["totals"]) == len(payload["labels"])
    # Deciles of all applicants: the matched of both runs add up to each run's matched.
    strength = charts["compare_strength"]["payload"]
    assert strength["whole"] is True
    for run, side in zip((finished_run, noisier_run), strength["runs"], strict=True):
        assert sum(side["counts"]) == run.metrics["outcomes"]["match"]["matched"]
        assert sum(side["totals"]) == 60
    # Choices are shares of each run's matched applicants.
    choice = charts["compare_choice"]["payload"]
    assert choice["whole"] is False
    for side in choice["runs"]:
        assert sum(side["values"]) == pytest.approx(1)
    assert charts["sorting_a"]["payload"]["sorting"] != charts["sorting_b"]["payload"]["sorting"]


def test_the_interviews_chart_takes_the_longer_run_s_bars(user, finished_run):
    """A run whose applicants accept more interviews has bars the other never reaches: those are empty, not absent."""
    more = run_now(_changed(_other_simulation(user), interview__applicant_cap=3), user)
    assert more.status == "succeeded", more.error
    chart = comparison_charts(RunData(finished_run), RunData(more))["compare_interviews"]
    payload = chart["payload"]
    most = [max(k for k, count in enumerate(run["counts"]) if count) for run in payload["runs"]]
    assert most[1] == 3
    assert most[0] > 3
    assert len(payload["labels"]) == most[0] + 1
    assert payload["runs"][1]["counts"][-1] == 0
    for run in payload["runs"]:
        assert sum(run["values"]) == pytest.approx(1)
    assert chart["rows"][-1]["b"] == 0
    assert chart["rows"][-1]["b_total"] == 60


def test_a_run_from_before_the_match_has_no_comparison_charts(finished_run, noisier_run):
    from nrmps.models import RunArtifact

    noisier_run.artifacts.filter(kind=RunArtifact.Kind.STAGES).delete()
    charts = comparison_charts(RunData(finished_run), RunData(noisier_run))
    assert set(charts) == {"compare_choice", "sorting_a"}  # the choices come from the diagnostics


# --- The page ---------------------------------------------------------------------------------------------------------


def test_the_page_asks_for_two_runs(auth_client, finished_run, noisier_run):
    body = auth_client.get(_url()).content.decode()
    assert "Choose two runs to compare" in body
    assert f'<option value="{run_key(finished_run)}">Test simulation: run 1</option>' in body
    assert f'<option value="{run_key(noisier_run)}">Test simulation: run 2</option>' in body
    assert "Key numbers" not in body
    assert "echarts" not in body
    one = auth_client.get(_url(finished_run)).content.decode()
    assert f'<option value="{run_key(finished_run)}" selected>' in one
    assert "Choose two runs to compare" in one
    assert "Swap A and B" not in one


def test_without_runs_the_page_points_to_the_demo(auth_client):
    body = auth_client.get(_url()).content.decode()
    assert "You have no finished run with a match yet" in body
    assert f'href="{reverse("nrmps:demo")}"' in body
    assert "<select" not in body


def test_the_page_compares_two_runs(auth_client, finished_run, noisier_run):
    response = auth_client.get(_url(finished_run, noisier_run))
    body = response.content.decode()
    for text in (
        "Compare two runs",
        "first differ at the Pre-interview stage",
        "Key numbers",
        "Programs&#x27; fidelity",
        "Both runs, question by question",
        "Who matched where, in each run",
        "A: Test simulation, run 1",
        "B: Test simulation, run 2",
        "Parameters that differ",
        "Program pre-interview noise",
        "Swap A and B",
    ):
        assert text in body, text
    assert response.context["rerun"] is False  # the same seed already
    assert RERUN_FORM not in body
    assert f'href="{_url(noisier_run, finished_run).replace("&", "&amp;")}"' in body  # swapped
    for key in ("compare_strength", "compare_choice", "compare_interviews", "compare_fill", "sorting"):
        assert escape(str(help_registry.CHARTS[key].title)) in body
    assert body.count('data-chart="versus"') == 4
    assert body.count('data-chart="heatmap"') == 2
    # The same chart twice: each with its own ids.
    for suffix in ("a", "b"):
        assert f'id="chart-sorting-{suffix}" type="application/json"' in body
        assert f'aria-describedby="chart-sorting-{suffix}-summary"' in body
        assert f'popovertarget="help-chart-sorting-{suffix}"' in body
    assert body.count("The numbers") == 6
    for text in ("vendor/echarts/6.1.0/echarts.min.js", "js/nrmp-charts.js"):
        assert text in body, text


def test_different_seeds_are_flagged_and_the_run_can_be_repeated_with_the_other_seed(
    auth_client, finished_run, other_seed_run
):
    response = auth_client.get(_url(finished_run, other_seed_run))
    body = response.content.decode()
    assert "can be chance alone" in body
    assert "alert-warning" in body
    assert response.context["rerun"] is True
    assert RERUN_FORM in body
    assert 'popovertarget="help-action-compare-rerun"' in body
    assert "Random seed" in body  # the only parameter that differs

    response = auth_client.post(
        reverse("nrmps:compare_rerun"), {"a": run_key(finished_run), "b": run_key(other_seed_run)}
    )
    simulation = other_seed_run.simulation
    new = simulation.runs.get(number=2)
    assert response["Location"] == _url(finished_run, new)
    assert new.status == "succeeded"
    assert new.seed == finished_run.seed
    assert simulation.runs.count() == 2  # run B itself stays
    simulation.refresh_from_db()
    assert simulation.get_params().run.seed == finished_run.seed
    # Same parameters and now the same seed: the two runs are the same.
    after = auth_client.get(response["Location"])
    assert after.context["pairing"].identical
    assert after.context["rerun"] is False
    assert "their results are the same" in after.content.decode()


def test_the_rerun_is_not_offered_when_the_simulation_has_changed(auth_client, finished_run, other_seed_run):
    _changed(other_seed_run.simulation, info__program_pre_noise_sd=2.5)
    response = auth_client.get(_url(finished_run, other_seed_run))
    assert response.context["rerun"] is False
    assert RERUN_FORM not in response.content.decode()


def test_the_rerun_reports_a_problem_and_stays_on_the_comparison(auth_client, settings, finished_run, other_seed_run):
    settings.NRMP_RUNS_PER_DAY = 0
    response = auth_client.post(
        reverse("nrmps:compare_rerun"), {"a": run_key(finished_run), "b": run_key(other_seed_run)}, follow=True
    )
    assert response.redirect_chain[-1][0] == _url(finished_run, other_seed_run)
    simulation = Simulation.objects.get(pk=other_seed_run.simulation_id)
    assert simulation.runs.count() == 1
    assert simulation.get_params().run.seed == 999  # the seed stays when the run could not start
    assert "alert-error" in response.content.decode()


def test_the_rerun_needs_two_runs(auth_client, finished_run):
    assert auth_client.post(reverse("nrmps:compare_rerun"), {"a": run_key(finished_run)}).status_code == 404
    assert auth_client.get(reverse("nrmps:compare_rerun")).status_code == 405


def test_the_same_run_twice_and_runs_without_a_match(auth_client, simulation, user, finished_run, monkeypatch):
    body = auth_client.get(_url(finished_run, finished_run)).content.decode()
    assert "A and B are the same run" in body
    assert "Key numbers" not in body
    monkeypatch.setattr("nrmps.runs.run_pipeline", lambda *a, **k: (_ for _ in ()).throw(ValueError("No luck.")))
    failed = run_now(simulation, user)
    assert failed.status == "failed"
    body = auth_client.get(_url(finished_run, failed)).content.decode()
    assert "Run 2 of “Test simulation” has no match to compare" in body
    assert "Key numbers" not in body
    assert f'value="{run_key(failed)}"' not in body  # not offered by the pickers either


def test_a_queued_run_is_waited_for(auth_client, simulation, user, finished_run):
    from nrmps.runs import start_run

    queued = start_run(simulation, user)
    response = auth_client.get(_url(finished_run, queued))
    body = response.content.decode()
    assert "Run 2 of “Test simulation” is queued" in body
    wait = reverse("nrmps:compare_wait") + f"?a={run_key(finished_run)}&amp;b={run_key(queued)}"
    assert f'hx-get="{wait}"' in body
    assert "Key numbers" not in body
    waiting = auth_client.get(wait.replace("&amp;", "&"))
    assert waiting.status_code == 204
    assert "HX-Refresh" not in waiting
    from nrmps.runs import execute_run

    execute_run(queued.pk)
    done = auth_client.get(wait.replace("&amp;", "&"))
    assert done["HX-Refresh"] == "true"
    assert "Key numbers" in auth_client.get(_url(finished_run, queued)).content.decode()


def test_other_users_runs_cannot_be_compared(client, other_user, finished_run, noisier_run):
    client.force_login(other_user)
    assert client.get(_url(finished_run, noisier_run)).status_code == 404
    assert client.get(_url(finished_run)).status_code == 404
    body = client.get(_url()).content.decode()
    assert "Test simulation" not in body
    response = client.post(reverse("nrmps:compare_rerun"), {"a": run_key(finished_run), "b": run_key(noisier_run)})
    assert response.status_code == 404
    assert finished_run.simulation.runs.count() == 2


def test_visitors_must_log_in_to_compare(client, finished_run):
    response = client.get(_url(finished_run))
    assert response.status_code == 302
    assert reverse("nrmps:login") in response["Location"]


def test_keys_that_are_not_keys_are_ignored_and_unknown_runs_are_not_found(auth_client, finished_run):
    assert auth_client.get(reverse("nrmps:compare") + "?a=nonsense&b=1-2-3").status_code == 200
    assert auth_client.get(reverse("nrmps:compare") + f"?a={finished_run.simulation_id}-99").status_code == 404


def test_run_pages_and_the_simulations_list_lead_to_the_comparison(auth_client, finished_run):
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number}
    for view in ("nrmps:run_detail", "nrmps:run_match", "nrmps:run_applicants"):
        body = auth_client.get(reverse(view, kwargs=kwargs)).content.decode()
        assert f'href="{_url(finished_run)}"' in body, view
    assert f'href="{reverse("nrmps:compare")}"' in auth_client.get(reverse("nrmps:simulation_list")).content.decode()


def test_the_comparison_has_its_help(auth_client, finished_run, noisier_run):
    body = auth_client.get(_url(finished_run, noisier_run)).content.decode()
    page = help_registry.PAGES["compare"]
    assert escape(str(page.title)) in body
    assert page.actions == ("compare_rerun",)
    assert 'popovertarget="help-column-compare-difference"' in body
    assert {key for key, chart in help_registry.CHARTS.items() if chart.tab == "compare"} == {
        "compare_strength",
        "compare_choice",
        "compare_interviews",
        "compare_fill",
    }
