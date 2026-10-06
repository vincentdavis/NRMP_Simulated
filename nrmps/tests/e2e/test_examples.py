"""The saved example runs in a browser: a visitor reads a run, follows an applicant and is led to the demo."""

import re

import pytest
from playwright.sync_api import expect

from nrmps.tests.e2e.test_pages import PHONE, _draw_every_chart, _overflow, _serious_violations

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

SMALL = "/examples/small-classroom-market/"
LARGE = "/examples/nrmp-like-market/"


def test_a_visitor_reads_an_example_and_is_led_to_the_demo(page, live):
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{live}/")
    page.get_by_role("link", name="See an example run", exact=True).click()
    page.wait_for_url(f"{live}/examples/")
    expect(page.get_by_role("heading", level=1)).to_have_text("Example runs")
    page.get_by_role("link", name="Open the small classroom market", exact=True).click()
    page.wait_for_url(live + SMALL)
    expect(page.get_by_role("heading", level=1)).to_contain_text("Small classroom market: a saved run")
    expect(page.get_by_role("heading", name="About this example")).to_be_visible()
    _draw_every_chart(page, 1)
    # The tabs, an applicant and the program they matched to are all pages of the example.
    tabs = page.get_by_role("navigation", name="Pages of this example")
    tabs.get_by_role("link", name="Match", exact=True).click()
    page.wait_for_url(f"{live}{SMALL}match/")
    expect(page.get_by_role("heading", level=1)).to_contain_text("Small classroom market: match")
    _draw_every_chart(page, 5)
    tabs.get_by_role("link", name="Applicants", exact=True).click()
    page.wait_for_url(f"{live}{SMALL}applicants/")
    page.get_by_role("link", name="Applicant 7", exact=True).click()
    page.wait_for_url(f"{live}{SMALL}applicants/7/")
    expect(page.get_by_role("heading", level=1)).to_contain_text("Applicant 7")
    _draw_every_chart(page, 2)
    page.get_by_role("region", name="In the match").get_by_role("link").first.click()
    page.wait_for_url(re.compile(rf"{re.escape(live + SMALL)}programs/\d+/"))
    _draw_every_chart(page, 2)
    page.get_by_role("link", name="All programs", exact=True).click()
    page.wait_for_url(f"{live}{SMALL}programs/")
    # Nothing here can be changed; changing the market means running it, which the demo offers.
    assert page.locator("form[method=post]").count() == 0
    page.get_by_role("link", name="Run this market yourself", exact=True).click()
    page.wait_for_url(f"{live}/demo/?preset=classroom")
    expect(page.get_by_role("radio", name=re.compile("^Small classroom market"))).to_be_checked()
    expect(page.get_by_role("button", name="Log in to run the demo", exact=True)).to_be_visible()
    assert errors == []


@pytest.mark.parametrize("base", [SMALL, LARGE])
@pytest.mark.parametrize(
    ("tab", "count"), [("", 1), ("population/", 3), ("before-interviews/", 6), ("applications/", 3), ("match/", 5)]
)
def test_an_examples_tabs_draw_every_chart_for_a_visitor(page, live, base, tab, count):
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(live + base + tab)
    _draw_every_chart(page, count)
    labels = page.locator("[data-chart]").evaluate_all("els => els.map((el) => el.getAttribute('aria-label') || '')")
    assert all(label.endswith("?") for label in labels), labels
    assert errors == []
    page.set_viewport_size(PHONE)
    page.wait_for_timeout(200)
    assert _overflow(page) <= 0


@pytest.mark.parametrize(
    "path", ["/examples/", SMALL, f"{SMALL}match/", f"{SMALL}applicants/7/", f"{LARGE}applications/"]
)
def test_the_examples_have_no_serious_accessibility_violations_in_the_dark_theme(page, live, path):
    page.emulate_media(color_scheme="dark")
    page.goto(live + path)
    page.wait_for_timeout(300)  # the theme's colours settle before they are measured
    assert _serious_violations(page) == []


def test_a_visitor_sorts_a_table_and_downloads_the_data(page, live):
    page.goto(f"{live}{SMALL}applicants/")
    rows = page.locator("table tbody tr")
    expect(rows).to_have_count(60)
    assert rows.first.locator("td").nth(1).inner_text() == "Applicant 1"
    page.get_by_role("link", name=re.compile("^Strength")).click()
    page.wait_for_url(re.compile(r"sort=strength"))
    page.get_by_role("link", name=re.compile("^Strength")).click()
    page.wait_for_url(re.compile(r"order=desc"))
    strengths = [float(text) for text in page.locator("table tbody tr td:nth-child(4)").all_inner_texts()]
    assert strengths == sorted(strengths, reverse=True)
    assert page.get_by_label("Rows per page").locator("option").all_inner_texts() == ["25", "50", "100"]
    with page.expect_download() as download:
        page.get_by_role("link", name="Download CSV", exact=True).click()
    assert download.value.suggested_filename == "small-classroom-market-applicants.csv"
    page.goto(live + SMALL)
    with page.expect_download() as download:
        page.get_by_role("link", name="The match: every applicant's result (CSV)", exact=True).click()
    assert download.value.suggested_filename == "small-classroom-market-match.csv"
