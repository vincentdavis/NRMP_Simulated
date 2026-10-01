"""Every page fits a 390 px phone screen and has no serious accessibility violations (plan step 1.4: UX-9, UX-19)."""

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect

from nrmps.guide import guide_pages

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

PUBLIC = [
    "/",
    "/contact/",
    "/privacy/",
    "/terms/",
    "/login/",
    "/signup/",
    "/demo/",
    # Every page of the guide (plan step 4.7: a new page is checked without editing this list).
    *(f"/help/{page.slug}/" if page.slug != "index" else "/help/" for page in guide_pages()),
    "/help/search/?q=interview",
    "/account/password/reset/",
    "/account/password/reset/sent/",
]
PRIVATE = [
    "/simulations/",
    "/simulations/new/",
    "/demo/",
    "/simulations/{pk}/",
    "/simulations/{pk}/runs/1/",
    "/simulations/{pk}/runs/1/population/",
    "/simulations/{pk}/runs/1/before-interviews/",
    "/simulations/{pk}/runs/1/applications/",
    "/simulations/{pk}/runs/1/match/",
    "/simulations/{pk}/runs/1/applicants/",
    "/simulations/{pk}/runs/1/programs/",
    "/simulations/{pk}/runs/1/applicants/1/",
    "/simulations/{pk}/runs/1/programs/1/",
    "/account/",
    "/account/edit/",
    "/account/delete/",
    "/account/password/",
]
PHONE = {"width": 390, "height": 844}


def _overflow(page) -> int:
    """Return how many pixels the page is wider than the viewport."""
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def _serious_violations(page) -> list[str]:
    results = Axe().run(page)
    return [
        f"{v['id']} ({v['impact']}): {v['help']} [{len(v['nodes'])} nodes: "
        f"{'; '.join(' '.join(map(str, node['target'])) for node in v['nodes'][:3])}]"
        for v in results.response["violations"]
        if v["impact"] in {"serious", "critical"}
    ]


@pytest.fixture
def worked_simulation(simulation, finished_run):
    """Return a simulation with one finished run."""
    return simulation


@pytest.mark.parametrize("path", PUBLIC)
def test_public_pages_fit_a_phone(page, live, path):
    page.set_viewport_size(PHONE)
    page.goto(live + path)
    assert _overflow(page) <= 0


@pytest.mark.parametrize("path", PRIVATE)
def test_private_pages_fit_a_phone(logged_in_page, live, worked_simulation, path):
    page = logged_in_page
    page.set_viewport_size(PHONE)
    page.goto(live + path.format(pk=worked_simulation.pk))
    assert _overflow(page) <= 0


@pytest.mark.parametrize("path", PUBLIC)
def test_public_pages_have_no_serious_accessibility_violations(page, live, path):
    page.goto(live + path)
    assert _serious_violations(page) == []


@pytest.mark.parametrize("path", PRIVATE)
def test_private_pages_have_no_serious_accessibility_violations(logged_in_page, live, worked_simulation, path):
    page = logged_in_page
    page.goto(live + path.format(pk=worked_simulation.pk))
    assert _serious_violations(page) == []


def _draw_every_chart(page, count: int) -> None:
    """Scroll each chart into view (they are drawn when they come near the screen) and wait until it is drawn."""
    charts = page.locator("[data-chart]")
    assert charts.count() == count
    for k in range(count):
        charts.nth(k).scroll_into_view_if_needed()
        expect(charts.nth(k).locator("canvas").first).to_be_attached()
    assert page.locator("[data-chart-failed]").count() == 0


@pytest.mark.parametrize(
    ("tab", "count"), [("", 1), ("population/", 3), ("before-interviews/", 6), ("applications/", 2)]
)
def test_the_run_tabs_draw_every_chart_without_script_errors(logged_in_page, live, worked_simulation, tab, count):
    """ECharts draws each chart as it comes into view (plan steps 3.8, 5.1), and again after the theme changes."""
    page = logged_in_page
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{live}/simulations/{worked_simulation.pk}/runs/1/{tab}")
    _draw_every_chart(page, count)
    page.evaluate("document.documentElement.dataset.theme = 'dark'")
    page.wait_for_timeout(200)
    assert page.locator("[data-chart] canvas").count() >= count
    # ECharts leaves the page's own label alone: each chart is named by its caption, the catalog's question.
    labels = page.locator("[data-chart]").evaluate_all("els => els.map((el) => el.getAttribute('aria-label') || '')")
    assert all(label.endswith("?") for label in labels), labels
    assert errors == []
    page.set_viewport_size(PHONE)
    page.wait_for_timeout(200)
    assert _overflow(page) <= 0


def test_new_simulation_page_has_no_serious_accessibility_violations(logged_in_page, live, simulation):
    """The page of a brand-new simulation (nothing run yet)."""
    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/")
    assert _serious_violations(page) == []
    page.set_viewport_size(PHONE)
    assert _overflow(page) <= 0


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/login/",
        "/simulations/{pk}/",
        "/simulations/{pk}/runs/1/",
        "/simulations/{pk}/runs/1/before-interviews/",
        "/simulations/{pk}/runs/1/applications/",
        "/simulations/{pk}/runs/1/applicants/1/",
    ],
)
def test_dark_theme_has_no_serious_accessibility_violations(logged_in_page, live, worked_simulation, path):
    page = logged_in_page
    page.emulate_media(color_scheme="dark")
    page.goto(live + path.format(pk=worked_simulation.pk))
    assert _serious_violations(page) == []


@pytest.mark.parametrize("side", ["applicants", "programs"])
def test_an_agents_page_draws_its_applications_as_a_network(logged_in_page, live, worked_simulation, side):
    """sigma.js draws one agent's applications by stage (plan step 5.1) and ECharts their funnel, again after the theme
    changes."""
    page = logged_in_page
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{live}/simulations/{worked_simulation.pk}/runs/1/{side}/1/")
    _draw_every_chart(page, 2)
    network = page.locator('[data-chart="ego"]')
    assert network.get_attribute("aria-label", timeout=1000).endswith("?")
    assert page.get_by_role("list", name="Key", exact=True).get_by_role("listitem").count() == 6
    page.evaluate("document.documentElement.dataset.theme = 'dark'")
    page.wait_for_timeout(200)
    expect(network.locator("canvas").first).to_be_attached()
    assert page.locator("[data-chart-failed]").count() == 0
    assert errors == []


# A program's funnel: its nodes, which way it runs, and how its drop-offs with applications are filled (a plain colour,
# or the fifths' colours as a linear gradient).
FUNNEL = """() => {
  const series = window.echarts.getInstanceByDom(document.querySelector('[data-chart="funnel"]')).getOption().series[0];
  const drops = series.data.filter((node) => !node.name.includes("|") && !node.name.startsWith("spacer:"));
  const fills = drops.filter((node) => node.label.formatter().match(/[1-9]/)).map((node) => (
    typeof node.itemStyle.color === "string" ? "plain" : node.itemStyle.color.type));
  return {nodes: series.data.length, orient: series.orient, fills: [...new Set(fills)]};
}"""


# A chart's node labels as drawn (ECharts' own geometry): how many, which fall outside the chart, which overlap another.
CHART_LABELS = """(selector) => {
  const chart = window.echarts.getInstanceByDom(document.querySelector(selector));
  const data = chart.getModel().getSeriesByIndex(0).getData();
  const rects = [];
  for (let i = 0; i < data.count(); i += 1) {
    const label = data.getItemGraphicEl(i)?.getTextContent();
    if (!label || label.ignore || label.invisible) continue;
    const r = label.getBoundingRect().clone();
    r.applyTransform(label.getComputedTransform());
    if (r.width >= 1) rects.push({name: data.getName(i), x: r.x, y: r.y, w: r.width, h: r.height});
  }
  const [W, H] = [chart.getWidth(), chart.getHeight()];
  const out = rects.filter((r) => r.x < -0.5 || r.y < -0.5 || r.x + r.w > W + 0.5 || r.y + r.h > H + 0.5);
  const overlaps = [];
  rects.forEach((a, i) => rects.slice(i + 1).forEach((b) => {
    if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) overlaps.push([a.name, b.name]);
  }));
  return {labels: rects.length, out: out.map((r) => r.name), overlaps};
}"""
CLEAN_FUNNEL_LABELS = {"labels": 9, "out": [], "overlaps": []}  # a label for each stage and each drop-off


def test_colour_by_strength_splits_a_programs_funnel(logged_in_page, live, worked_simulation):
    """The switch on a program's page splits its funnel by the strength fifth of its applicants, wide and at phone
    width (where it runs top to bottom), and the choice is shared with the applicants' flow. At phone width the labels,
    with the switch on or off, stay inside the chart and apart."""
    page = logged_in_page
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{live}/simulations/{worked_simulation.pk}/runs/1/programs/1/")
    funnel = page.locator('[data-chart="funnel"]')
    funnel.scroll_into_view_if_needed()
    expect(funnel.locator("canvas").first).to_be_attached()
    assert page.evaluate(FUNNEL)["nodes"] == 9  # five stages and four drop-offs
    page.get_by_role("switch", name="Colour by strength").check()
    expect(page.locator('[data-chart-switch-key="bands"]')).to_be_visible()
    # Each of the five stages in five fifths, and the four drop-offs, each after a transparent spacer.
    assert page.evaluate(FUNNEL) == {"nodes": 33, "orient": "horizontal", "fills": ["linear"]}
    assert funnel.get_attribute("data-chart-failed") is None
    page.set_viewport_size(PHONE)
    page.wait_for_timeout(300)
    assert page.evaluate(FUNNEL) == {"nodes": 33, "orient": "vertical", "fills": ["linear"]}
    assert funnel.get_attribute("data-chart-failed") is None
    assert page.evaluate(CHART_LABELS, '[data-chart="funnel"]') == CLEAN_FUNNEL_LABELS
    assert _overflow(page) <= 0
    page.goto(f"{live}/simulations/{worked_simulation.pk}/runs/1/applications/")  # the same switch, remembered
    expect(page.get_by_role("switch", name="Colour by strength")).to_be_checked()
    page.go_back()
    funnel = page.locator('[data-chart="funnel"]')
    funnel.scroll_into_view_if_needed()
    expect(funnel.locator("canvas").first).to_be_attached()
    page.get_by_role("switch", name="Colour by strength").uncheck()  # off, at phone width: the same label layout
    assert page.evaluate(FUNNEL)["orient"] == "vertical"
    assert page.evaluate(FUNNEL)["nodes"] == 9
    assert page.evaluate(CHART_LABELS, '[data-chart="funnel"]') == CLEAN_FUNNEL_LABELS
    assert errors == []


FLOW_NODES = """() => {
  const chart = window.echarts.getInstanceByDom(document.querySelector('[data-chart="flow"]'));
  return chart.getOption().series[0].data.length;
}"""

# How the "No interview" drop-off is filled (a plain colour, or the fifths' colours as a linear gradient whose stops
# end at 1), and what hovering highlights.
FLOW_DROP = """() => {
  const series = window.echarts.getInstanceByDom(document.querySelector('[data-chart="flow"]')).getOption().series[0];
  const color = series.data.find((node) => node.name === "No interview").itemStyle.color;
  const stops = typeof color === "string" ? [] : color.colorStops;
  return {fill: typeof color === "string" ? "plain" : color.type, end: stops.length ? stops.at(-1).offset : null,
          focus: series.emphasis.focus};
}"""


def test_the_summary_shows_the_flow_split_by_strength_until_turned_off(logged_in_page, live, worked_simulation):
    """The summary's applicants' flow starts split by strength; turning the switch off is remembered, there and on the
    Applications and interviews tab."""
    page = logged_in_page
    summary = f"{live}/simulations/{worked_simulation.pk}/runs/1/"
    page.goto(summary)
    flow = page.locator('[data-chart="flow"]')
    flow.scroll_into_view_if_needed()
    expect(flow.locator("canvas").first).to_be_attached()
    assert page.evaluate(FLOW_NODES) == 19  # five fifths per stage, two drop-offs and their spacers
    expect(page.locator('[data-chart-switch-key="bands"]')).to_be_visible()
    page.get_by_role("switch", name="Colour by strength").uncheck()
    assert page.evaluate(FLOW_NODES) == 5
    page.goto(summary)
    page.locator('[data-chart="flow"]').scroll_into_view_if_needed()
    expect(page.locator('[data-chart="flow"] canvas').first).to_be_attached()
    expect(page.get_by_role("switch", name="Colour by strength")).not_to_be_checked()
    assert page.evaluate(FLOW_NODES) == 5


def test_colour_by_strength_splits_the_applicants_flow_and_is_remembered(logged_in_page, live, worked_simulation):
    """The switch splits the applicants' flow into strength fifths, drop-offs included, shows its key and stays on."""
    page = logged_in_page
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    url = f"{live}/simulations/{worked_simulation.pk}/runs/1/applications/"
    page.goto(url)
    flow = page.locator('[data-chart="flow"]')
    flow.scroll_into_view_if_needed()
    expect(flow.locator("canvas").first).to_be_attached()
    assert page.evaluate(FLOW_NODES) == 5  # three stages and two drop-offs
    assert page.evaluate(FLOW_DROP) == {"fill": "plain", "end": None, "focus": "trajectory"}
    switch = page.get_by_role("switch", name="Colour by strength")
    key = page.locator('[data-chart-switch-key="bands"]')
    expect(key).to_be_hidden()
    switch.check()
    expect(key).to_be_visible()
    # Each of the three stages in five fifths, and the two drop-offs, each after a transparent spacer.
    assert page.evaluate(FLOW_NODES) == 19
    assert page.evaluate(FLOW_DROP) == {"fill": "linear", "end": 1, "focus": "trajectory"}
    assert flow.get_attribute("data-chart-failed") is None
    page.reload()  # drawn with the switch already on (a redraw keeps the old canvas even when the new option fails)
    flow = page.locator('[data-chart="flow"]')
    flow.scroll_into_view_if_needed()
    expect(flow.locator("canvas").first).to_be_attached()
    expect(page.get_by_role("switch", name="Colour by strength")).to_be_checked()
    assert page.evaluate(FLOW_NODES) == 19
    assert flow.get_attribute("data-chart-failed") is None
    page.evaluate("document.documentElement.dataset.chartPatterns = 'on'")  # patterns: the spacers get none
    page.wait_for_timeout(200)
    assert flow.get_attribute("data-chart-failed") is None
    page.evaluate("document.documentElement.dataset.chartPatterns = 'off'")
    page.set_viewport_size(PHONE)  # narrowing redraws it in its phone layout: labels on two lines, more room on top
    page.wait_for_timeout(300)
    assert page.evaluate(FLOW_NODES) == 19
    assert page.evaluate(FLOW_NODES.replace("data.length", "top")) == 44
    assert _overflow(page) <= 0
    page.get_by_role("switch", name="Colour by strength").uncheck()
    assert page.evaluate(FLOW_NODES) == 5
    expect(page.locator('[data-chart-switch-key="bands"]')).to_be_hidden()
    assert errors == []
