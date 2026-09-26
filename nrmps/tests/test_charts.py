"""Diagnostic chart payloads (plan step 3.8): requested against realised, samples, demand and the funnel."""

import json

import numpy as np
import pytest
from django.urls import reverse

from nrmps.charts import digits, fit_check, funnel, gini, perception_samples, requested_histogram, run_charts
from nrmps.engine.metrics import histogram
from nrmps.engine.population import generate_population
from nrmps.models import RunArtifact, SimulationRun
from nrmps.params import SimulationParams
from nrmps.runs import RunData

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


def test_the_run_page_embeds_the_charts_and_their_numbers(auth_client, finished_run):
    url = reverse("nrmps:run_detail", kwargs={"pk": finished_run.simulation_id, "number": finished_run.number})
    body = auth_client.get(url).content.decode()
    for text in (
        'data-chart="funnel"',
        'id="chart-strength"',
        'data-payload="chart-demand"',
        "vendor/echarts/6.1.0/echarts.min.js",
        "js/nrmp-charts.js",
        "Where do applications drop out?",
        'aria-describedby="chart-funnel-summary"',
        "The numbers",
    ):
        assert text in body, text
    assert body.count("data-chart=") == 10


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
