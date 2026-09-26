"""Every page fits a 390 px phone screen and has no serious accessibility violations (plan step 1.4: UX-9, UX-19)."""

import pytest
from axe_playwright_python.sync_playwright import Axe

from nrmps import simulation_engine as se

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

PUBLIC = ["/", "/contact/", "/privacy/", "/terms/", "/login/", "/signup/", "/documentation/"]
PRIVATE = [
    "/simulations/",
    "/simulations/new/",
    "/simulations/{pk}/",
    "/simulations/{pk}/students/",
    "/simulations/{pk}/schools/",
    "/simulations/{pk}/interviews/",
    "/account/",
    "/account/password/",
]
PHONE = {"width": 390, "height": 844}


def _overflow(page) -> int:
    """Return how many pixels the page is wider than the viewport."""
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def _serious_violations(page) -> list[str]:
    results = Axe().run(page)
    return [
        f"{v['id']} ({v['impact']}): {v['help']} [{len(v['nodes'])} nodes]"
        for v in results.response["violations"]
        if v["impact"] in {"serious", "critical"}
    ]


@pytest.fixture
def worked_simulation(populated_simulation):
    """Return a simulation with populations, interview rows and pre-interview ranks."""
    se.initialize_interview(populated_simulation)
    se.compute_pre_interview_scores_and_rankings(populated_simulation)
    return populated_simulation


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


def test_new_simulation_page_has_no_serious_accessibility_violations(logged_in_page, live, simulation):
    """The manage page of a brand-new simulation (stage "setup": most cards locked or planned)."""
    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/")
    assert _serious_violations(page) == []
    page.set_viewport_size(PHONE)
    assert _overflow(page) <= 0


@pytest.mark.parametrize("path", ["/", "/login/", "/simulations/{pk}/", "/simulations/{pk}/interviews/"])
def test_dark_theme_has_no_serious_accessibility_violations(logged_in_page, live, worked_simulation, path):
    page = logged_in_page
    page.emulate_media(color_scheme="dark")
    page.goto(live + path.format(pk=worked_simulation.pk))
    assert _serious_violations(page) == []
