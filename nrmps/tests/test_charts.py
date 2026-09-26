"""Diagnostic chart payloads (plan step 3.8): requested against realised, samples, demand and the funnel."""

import json

import numpy as np
import pytest
from django.urls import reverse
from django.utils.html import escape

from nrmps import help_registry
from nrmps.charts import (
    EGO_MAX_NODES,
    agent_funnel,
    digits,
    ego_network,
    fit_check,
    funnel,
    gini,
    perception_samples,
    requested_histogram,
    run_charts,
)
from nrmps.engine.metrics import histogram
from nrmps.engine.population import generate_population
from nrmps.models import RunArtifact, SimulationRun
from nrmps.params import SimulationParams
from nrmps.runs import RunData, StageRows

TIERS = [{"name": "top", "share": 0.2, "quality_mean": 1.5}, {"name": "rest", "share": 0.8, "quality_mean": -0.4}]

pytestmark = pytest.mark.django_db


def test_every_chart_of_a_run(finished_run):
    charts = run_charts(RunData(finished_run))
    assert set(charts) == {
        "strength",
        "quality",
        "capacity",
        "applicant_fidelity",
        "program_fidelity",
        "perception_applicants",
        "perception_programs",
        "demand",
        "lorenz",
        "funnel",
    }
    for chart in charts.values():
        assert chart["summary"]
    json.dumps({key: chart["payload"] for key, chart in charts.items()})  # plain JSON


def test_the_requested_distribution_matches_what_was_generated(finished_run):
    charts = run_charts(RunData(finished_run))
    for key, total in (("strength", 60), ("quality", 8)):
        payload = charts[key]["payload"]
        assert sum(payload["counts"]) == total
        assert sum(payload["requested"]) == pytest.approx(total, abs=0.1)
    assert charts["capacity"]["payload"].get("requested") is None


@pytest.mark.parametrize("side", ["applicants", "programs"])
def test_a_large_generated_market_follows_the_request(side):
    params = SimulationParams.model_validate(
        {"market": {"n_applicants": 20_000, "n_programs": 2_000}, "programs": {"tiers": TIERS}}
    )
    population = generate_population(params, 4)
    metrics = {
        "histograms": {
            "strength": histogram(population.applicants.strength),
            "quality": histogram(population.programs.quality),
        }
    }
    payload = requested_histogram(metrics, params, {"applicants": "generated", "programs": "generated"}, side)
    assert fit_check(payload) < 4


def test_a_bad_generator_would_show():
    payload = {"counts": [0, 50, 0], "requested": [25.0, 0.0, 25.0], "edges": [0, 1, 2, 3]}
    assert fit_check(payload) == 5.0
    assert fit_check({"counts": [1], "requested": [1.0]}) is None  # too few expected to judge
    assert fit_check({"counts": [1], "requested": None}) is None


def test_uploaded_sides_have_no_requested_distribution(finished_run):
    SimulationRun.objects.filter(pk=finished_run.pk).update(
        population_source={"applicants": "mine.csv", "programs": "generated"}
    )
    finished_run.refresh_from_db()
    charts = run_charts(RunData(finished_run))
    assert charts["strength"]["payload"]["requested"] is None
    assert charts["strength"]["deviation"] is None
    assert charts["quality"]["payload"]["requested"] is not None


def test_bin_labels_get_enough_decimals():
    assert digits([0.0, 0.5, 1.0]) == 2
    assert digits([0.88, 0.8805, 0.881]) == 5
    assert digits([3.0, 19.5, 36.0]) == 0


def test_gini():
    assert gini(np.array([5, 5, 5, 5])) == pytest.approx(0.0)
    assert gini(np.array([0, 0, 0, 12])) == pytest.approx(0.75)
    assert gini(np.array([0, 0])) is None


def test_the_funnel_adds_up(finished_run):
    data = RunData(finished_run)
    counts = funnel(data.stages)
    assert counts["applied"] == counts["invited"] + counts["not_invited"]
    assert counts["invited"] == counts["interviewed"] + counts["declined"]
    assert counts["interviewed"] == counts["ranked"] + counts["not_ranked"]
    assert counts["ranked"] == counts["matched"] + counts["not_matched"]
    assert counts["matched"] == finished_run.metrics["outcomes"]["match"]["matched"]
    assert funnel(None) is None


def test_the_scatter_sample_repeats_and_is_bounded(finished_run):
    data = RunData(finished_run)
    first, again = perception_samples(data, size=100), perception_samples(RunData(finished_run), size=100)
    assert first == again
    assert len(first["applicants"]["pre"][0]) == 100
    assert len(first["applicants"]["post"][0]) <= 100
    small = perception_samples(data, size=10_000)  # 480 pairs: every pair once
    assert len(small["programs"]["pre"][0]) == 480


@pytest.mark.parametrize(
    ("view", "kinds"),
    [
        ("run_population", {"strength", "quality", "capacity"}),
        ("run_pre_interview", {"applicant-fidelity", "program-fidelity", "perception-applicants", "demand"}),
        ("run_applications", {"funnel"}),
    ],
)
def test_the_run_tabs_embed_their_charts_and_numbers(auth_client, finished_run, view, kinds):
    url = reverse(f"nrmps:{view}", kwargs={"pk": finished_run.simulation_id, "number": finished_run.number})
    body = auth_client.get(url).content.decode()
    for key in kinds:
        assert f'id="chart-{key}"' in body, key
        assert f'aria-describedby="chart-{key}-summary"' in body, key
    for text in ("vendor/echarts/6.1.0/echarts.min.js", "js/nrmp-charts.js"):
        assert text in body, text


def test_the_summary_tab_loads_no_chart_code(auth_client, finished_run):
    url = reverse("nrmps:run_detail", kwargs={"pk": finished_run.simulation_id, "number": finished_run.number})
    assert b"echarts" not in auth_client.get(url).content


def test_runs_without_results_load_no_chart_code(auth_client, simulation, user, monkeypatch):
    from nrmps.runs import run_now

    monkeypatch.setattr("nrmps.runs.run_pipeline", lambda *a, **k: (_ for _ in ()).throw(ValueError("No luck.")))
    run = run_now(simulation, user)
    body = auth_client.get(reverse("nrmps:run_detail", kwargs={"pk": simulation.pk, "number": run.number})).content
    assert b"echarts" not in body
    assert b"data-chart" not in body


def test_runs_from_before_the_match_draw_the_population_charts(auth_client, finished_run):
    finished_run.artifacts.filter(kind=RunArtifact.Kind.STAGES).delete()
    charts = run_charts(RunData(finished_run))
    assert "funnel" not in charts
    assert charts["perception_applicants"]["payload"]["post"] is None


# --- Plan step 5.1: the chart catalog and the network of one agent ---------------------------------------------------


def test_every_chart_on_the_run_tabs_has_its_question_and_help(auth_client, finished_run):
    """Captions and "?" popovers come from the chart catalog; each chart carries its colour role."""
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number}
    shown = set()
    for view in ("nrmps:run_population", "nrmps:run_pre_interview", "nrmps:run_applications"):
        body = auth_client.get(reverse(view, kwargs=kwargs)).content.decode()
        for key, chart in help_registry.CHARTS.items():
            if f'popovertarget="help-chart-{key.replace("_", "-")}"' in body:
                shown.add(key)
                assert escape(str(chart.title)) in body
        assert 'data-series="program"' in body or view == "nrmps:run_applications"
    assert shown == {key for key, chart in help_registry.CHARTS.items() if chart.tab != "agent"}


def _stage_rows(**changes):
    rows = StageRows.empty(10)
    rows.applied[:8] = True
    rows.wave[:5] = 1
    rows.interviewed[:4] = True
    rows.list_rank[:3] = [1, 2, 3]
    rows.matched[1] = True
    for name, value in changes.items():
        setattr(rows, name, value)
    return rows


def test_the_network_places_each_application_at_the_stage_it_reached():
    names = [f"Program {k}" for k in range(10)]
    chart = ego_network(_stage_rows(), names, "Ann", applicant=True)
    stages = dict(chart["payload"]["nodes"])
    assert stages == {
        "Program 1": 4,  # matched
        "Program 0": 3,  # ranked, not matched
        "Program 2": 3,
        "Program 3": 2,  # interviewed, not ranked
        "Program 4": 1,  # invited, no interview
        "Program 5": 0,  # applied only
        "Program 6": 0,
        "Program 7": 0,
    }
    assert [node[1] for node in chart["payload"]["nodes"]] == sorted(stages.values(), reverse=True)
    assert chart["summary"] == (
        "Ann's 8 applications by how far each got: 1 matched; 2 ranked, not matched; 1 interviewed, not ranked; "
        "1 invited, no interview; 3 not invited."
    )
    assert [item.get("count") for item in chart["legend"]] == [None, 3, 1, 1, 2, 1]
    assert chart["legend"][0] == {"label": "This applicant", "dot": "viz-dot-series-1"}


def test_the_network_of_a_program_and_its_limits():
    names = [f"Applicant {k}" for k in range(10)]
    chart = ego_network(_stage_rows(), names, "General", applicant=False)
    assert chart["payload"]["side"] == "program"
    assert chart["summary"].startswith("The 8 applications to General by how far each got")
    assert ego_network(StageRows.empty(10), names, "Empty", applicant=False) is None


def test_a_large_network_keeps_the_applications_that_got_furthest(monkeypatch):
    monkeypatch.setattr("nrmps.charts.EGO_MAX_NODES", 5)
    names = [f"Applicant {k}" for k in range(10)]
    chart = ego_network(_stage_rows(), names, "General", applicant=False)
    assert [node[1] for node in chart["payload"]["nodes"]] == [4, 3, 3, 2, 1]
    assert chart["summary"].endswith("The network shows the 5 that got furthest.")
    assert EGO_MAX_NODES >= 1000  # the real limit leaves room for large programs


def test_the_agent_pages_embed_the_network_and_load_its_libraries(auth_client, finished_run):
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number, "index": 1}
    for view, key in (("nrmps:run_applicant", "ego_applicant"), ("nrmps:run_program", "ego_program")):
        body = auth_client.get(reverse(view, kwargs=kwargs)).content.decode()
        assert 'data-chart="ego"' in body
        assert escape(str(help_registry.CHARTS[key].title)) in body
        assert "vendor/sigma/3.0.3/sigma.min.js" in body
        assert "vendor/graphology/0.26.0/graphology.umd.min.js" in body
        assert "vendor/echarts/6.1.0/echarts.min.js" in body  # for the funnel beside the network
        side = key.removeprefix("ego_")
        script = body.split(f'id="chart-ego-{side}" type="application/json">')[1].split("</script>")[0]
        assert json.loads(script)["side"] == side


def test_an_agents_funnel_matches_its_network(finished_run):
    """The funnel on an agent's page counts the same applications as its network, stage by stage."""
    data = RunData(finished_run)
    population = data.population
    for applicant in (True, False):
        others = population.programs if applicant else population.applicants
        names = [others.name(k) for k in range(others.size)]
        stages = data.stage_rows(0, applicant=applicant)
        funnel_chart = agent_funnel(stages, "Agent", applicant=applicant)
        network = ego_network(stages, names, "Agent", applicant=applicant)
        counts = funnel_chart["payload"]
        exclusive = [item["count"] for item in network["legend"][1:]]  # not invited ... matched
        assert exclusive == [
            counts["not_invited"],
            counts["declined"],
            counts["not_ranked"],
            counts["not_matched"],
            counts["matched"],
        ]
        assert counts["applied"] == sum(exclusive)
        whose = "applicant's" if applicant else "program's"
        assert f"to a place on the {whose} rank order list" in funnel_chart["summary"]
        assert funnel_chart["rows"][3]["stage"] == f"On the {whose} list"


def test_an_agent_without_applications_has_no_funnel():
    assert agent_funnel(StageRows.empty(5), "Nobody", applicant=True) is None


def test_the_agent_pages_show_the_funnel_with_its_numbers(auth_client, finished_run):
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number, "index": 1}
    for view, key in (("nrmps:run_applicant", "funnel_applicant"), ("nrmps:run_program", "funnel_program")):
        body = auth_client.get(reverse(view, kwargs=kwargs)).content.decode()
        assert 'data-chart="funnel"' in body
        assert escape(str(help_registry.CHARTS[key].title)) in body
        assert "The numbers" in body
