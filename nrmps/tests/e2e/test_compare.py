"""Comparing two runs in a real browser: the pickers, the charts with both runs, the same-seed run, phone and axe."""

import re

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect

from nrmps.models import Simulation
from nrmps.params import load_params
from nrmps.runs import run_now
from nrmps.tests.conftest import SMALL_PARAMS

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

PHONE = {"width": 390, "height": 844}

# The comparison's charts as drawn: the series of each chart with both runs, and the two heatmaps' cells and scales.
CHARTS = """() => {
  const option = (element) => window.echarts.getInstanceByDom(element).getOption();
  const versus = [...document.querySelectorAll('[data-chart="versus"]')].map(option);
  const heat = [...document.querySelectorAll('[data-chart="heatmap"]')].map(option);
  return {
    series: versus.map((chart) => chart.series.map((series) => series.name).join("")),
    colours: new Set(versus.flatMap((chart) => chart.series.map((series) => series.itemStyle.color))).size,
    whole: versus.map((chart) => chart.yAxis[0].max === 1),
    cells: heat.map((chart) => chart.series.map((series) => series.data.length)),
    scales: heat.map((chart) => chart.visualMap.map((map) => [map.min, map.max])),
  };
}"""


def _serious_violations(page) -> list[str]:
    results = Axe().run(page)
    return [
        f"{v['id']} ({v['impact']}): {v['help']} "
        f"[{'; '.join(' '.join(map(str, node['target'])) for node in v['nodes'][:3])}]"
        for v in results.response["violations"]
        if v["impact"] in {"serious", "critical"}
    ]


def _overflow(page) -> int:
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def _draw_every_chart(page, count: int) -> None:
    charts = page.locator("[data-chart]")
    assert charts.count() == count
    for k in range(count):
        charts.nth(k).scroll_into_view_if_needed()
        expect(charts.nth(k).locator("canvas").first).to_be_attached()
    assert page.locator("[data-chart-failed]").count() == 0


@pytest.fixture
def noisier_run(simulation, user, finished_run):
    """Return a second run of the simulation: the same seed, noisier programs."""
    data = simulation.get_params().to_json_data()
    data["info"]["program_pre_noise_sd"] = 2.5
    simulation.set_params(load_params(data))
    simulation.save()
    run = run_now(simulation, user)
    assert run.status == "succeeded", run.error
    return run


@pytest.fixture
def other_seed_run(user):
    """Return a run of another simulation with the same parameters and another seed."""
    params = load_params(SMALL_PARAMS | {"run": {"seed": 999}}).to_json_data()
    run = run_now(Simulation.objects.create(owner=user, name="Another seed", params=params), user)
    assert run.status == "succeeded", run.error
    return run


def test_the_comparison_draws_both_runs_and_fits_a_phone(logged_in_page, live, finished_run, noisier_run):
    """Four charts with both runs (A and B as two series, in two colours) and the two heatmaps on the same scale;
    no serious accessibility violation in either theme; no sideways scrolling on a phone."""
    page = logged_in_page
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{live}/compare/?a={finished_run.simulation_id}-1&b={finished_run.simulation_id}-2")
    expect(page.get_by_role("heading", level=1)).to_have_text("Compare two runs")
    expect(page.get_by_role("note", name="What the runs share")).to_contain_text("first differ at the Pre-interview")
    _draw_every_chart(page, 6)
    assert page.evaluate(CHARTS) == {
        "series": ["AB"] * 4,
        "colours": 2,
        "whole": [True, False, False, True],  # shares of a decile or a fifth; shares of a run's total
        "cells": [[5, 25], [5, 25]],
        "scales": [[[0, 1], [0, 1]]] * 2,
    }
    assert _serious_violations(page) == []
    page.evaluate("document.documentElement.dataset.chartPatterns = 'on'")
    page.wait_for_timeout(200)
    assert page.locator("[data-chart-failed]").count() == 0
    page.evaluate("document.documentElement.dataset.chartPatterns = 'off'")
    page.emulate_media(color_scheme="dark")
    page.wait_for_timeout(200)
    assert _serious_violations(page) == []
    page.set_viewport_size(PHONE)
    page.wait_for_timeout(300)
    assert page.locator("[data-chart-failed]").count() == 0
    assert _overflow(page) <= 0
    assert errors == []


def test_choosing_two_runs_in_the_pickers_compares_them(logged_in_page, live, finished_run, noisier_run):
    """From a run's page: Compare opens the page with the run as A; choosing B shows the comparison; Swap swaps."""
    page = logged_in_page
    sim = finished_run.simulation_id
    page.goto(f"{live}/simulations/{sim}/runs/1/match/")
    page.get_by_role("link", name="Compare", exact=True).click()
    page.wait_for_url(f"{live}/compare/?a={sim}-1")
    expect(page.get_by_label("Run A", exact=True)).to_have_value(f"{sim}-1")
    expect(page.get_by_role("status")).to_contain_text("Choose two runs to compare")
    assert _serious_violations(page) == []
    page.get_by_label("Run B", exact=True).select_option(f"{sim}-2")  # the select submits the form
    page.wait_for_url(f"{live}/compare/?a={sim}-1&b={sim}-2")
    expect(page.get_by_role("heading", name="Key numbers")).to_be_visible()
    expect(page.get_by_role("region", name="Parameters that differ between the runs")).to_contain_text(
        "Program pre-interview noise"
    )
    page.get_by_role("link", name="Swap A and B").click()
    page.wait_for_url(f"{live}/compare/?a={sim}-2&b={sim}-1")
    expect(page.get_by_label("Run A", exact=True)).to_have_value(f"{sim}-2")


def test_runs_with_different_seeds_can_be_run_again_with_the_same_seed(
    logged_in_page, live, finished_run, other_seed_run
):
    """The note warns that the seeds differ; "Run B again with A's seed" runs B's simulation with A's seed and shows
    the comparison with the new run, which is then the same as A (the two simulations have the same parameters)."""
    page = logged_in_page
    a, b = finished_run.simulation_id, other_seed_run.simulation_id
    page.goto(f"{live}/compare/?a={a}-1&b={b}-1")
    note = page.get_by_role("note", name="What the runs share")
    expect(note).to_contain_text("can be chance alone")
    assert _serious_violations(page) == []
    page.emulate_media(color_scheme="dark")
    page.wait_for_timeout(300)  # the theme's colours fade in
    assert _serious_violations(page) == []  # the button and its "?" inside the coloured note
    page.set_viewport_size(PHONE)
    assert _overflow(page) <= 0
    note.get_by_role("button", name="Help: Run B again with A's seed").click()
    expect(page.get_by_role("note", name="Run B again with A's seed")).to_be_visible()
    page.keyboard.press("Escape")
    note.get_by_role("button", name="Run B again with A's seed", exact=True).click()
    page.wait_for_url(re.compile(rf"/compare/\?a={a}-1&b={b}-2$"))
    expect(page.locator("#toasts")).to_contain_text("uses the seed of run A")
    expect(page.get_by_role("note", name="What the runs share")).to_contain_text("their results are the same")
    assert other_seed_run.simulation.runs.get(number=2).seed == finished_run.seed
