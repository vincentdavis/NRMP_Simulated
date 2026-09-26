"""In a real browser: names from uploaded files never become markup in chart tooltips, and the Content Security
Policy is live (plan step 5.1: VIZ-12, ENG-22)."""

import csv
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from playwright.sync_api import expect

from nrmps.engine.population import generate_population
from nrmps.models import PopulationUpload
from nrmps.population_csv import digest, parse_population_csv, population_csv_lines
from nrmps.runs import run_now

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

NAME = '<img src=x onerror="window.nrmpInjected=1">Evil program'


def _upload_programs_with_markup(simulation) -> None:
    """Replace the simulation's programs with generated ones, the first renamed to carry markup."""
    params = simulation.get_params()
    lines = list(population_csv_lines(generate_population(params, 12345).programs))
    rows = list(csv.reader(io.StringIO("".join(lines))))
    rows[1][0] = NAME
    text = io.StringIO()
    csv.writer(text).writerows(rows)
    file = SimpleUploadedFile("programs.csv", text.getvalue().encode(), "text/csv")
    upload = parse_population_csv(file, "programs", params)
    data = upload.to_npz()
    PopulationUpload.objects.create(
        simulation=simulation,
        side="programs",
        filename="programs.csv",
        rows=upload.rows,
        data=data,
        digest=digest(data),
    )


def test_markup_in_an_uploaded_name_stays_text_in_chart_tooltips(logged_in_page, live, simulation, user):
    _upload_programs_with_markup(simulation)
    run = run_now(simulation, user)
    assert run.status == "succeeded", run.error
    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/runs/1/before-interviews/")
    chart = page.locator('[data-chart="demand"]')
    chart.scroll_into_view_if_needed()
    expect(chart.locator("canvas").first).to_be_attached()
    names = page.evaluate("JSON.parse(document.getElementById('chart-demand').textContent).names")
    index = names.index(NAME)
    page.evaluate(
        """(index) => {
          const chart = window.echarts.getInstanceByDom(document.querySelector('[data-chart="demand"]'));
          chart.dispatchAction({ type: "showTip", seriesIndex: 0, dataIndex: index });
        }""",
        index,
    )
    tooltip = chart.locator("div", has_text="Evil program").last
    expect(tooltip).to_contain_text('<img src=x onerror="window.nrmpInjected=1">Evil program')
    assert page.locator('img[src="x"]').count() == 0
    assert page.evaluate("window.nrmpInjected") is None


def test_the_policy_reports_what_it_would_block(page, live, csp_violations):
    """The report-only policy is active: an inline script without the page's nonce is reported (and, report-only,
    still runs)."""
    page.goto(f"{live}/")
    page.evaluate(
        """() => {
          const script = document.createElement("script");
          script.textContent = "window.nrmpInlineRan = true";
          document.body.append(script);
        }"""
    )
    page.wait_for_function("window.nrmpInlineRan === true")
    page.wait_for_timeout(200)
    assert any(violation.startswith("script-src") for violation in csp_violations), csp_violations
    csp_violations.clear()  # expected here; the fixture fails any test that leaves violations
