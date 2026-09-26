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


@pytest.mark.parametrize(("tab", "count"), [("population", 3), ("before-interviews", 6), ("applications", 1)])
def test_the_run_tabs_draw_every_chart_without_script_errors(logged_in_page, live, worked_simulation, tab, count):
    """ECharts draws each chart as it comes into view (plan steps 3.8, 5.1), and again after the theme changes."""
    page = logged_in_page
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{live}/simulations/{worked_simulation.pk}/runs/1/{tab}/")
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
    assert page.get_by_role("list", name="Key").get_by_role("listitem").count() == 6
    page.evaluate("document.documentElement.dataset.theme = 'dark'")
    page.wait_for_timeout(200)
    expect(network.locator("canvas").first).to_be_attached()
    assert page.locator("[data-chart-failed]").count() == 0
    assert errors == []
