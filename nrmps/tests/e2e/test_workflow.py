"""The workflow runs in a real browser: HTMX step buttons, confirm dialogs and the Alpine tag editor."""

import re

import pytest
from playwright.sync_api import expect

from nrmps.models import Interview, Simulation

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _confirm(page):
    """Accept the site's confirmation dialog."""
    page.get_by_role("dialog").get_by_role("button", name="Continue").click()


def test_steps_run_from_the_page(logged_in_page, live):
    page = logged_in_page

    page.goto(f"{live}/simulations/new/")
    page.fill("#id_name", "Browser run")
    page.get_by_role("button", name="Create", exact=True).click()
    page.wait_for_url(re.compile(r"/simulations/\d+/$"))
    expect(page.locator("#toasts")).to_contain_text("Simulation created")
    sim = Simulation.objects.get(name="Browser run")

    # Make the market small so the steps are quick, through the real configuration form.
    page.fill("#id_number_of_applicants", "30")
    page.fill("#id_number_of_schools", "5")
    page.get_by_role("button", name="Save configuration").click()
    expect(page.locator("#toasts")).to_contain_text("Configuration saved")

    cards = page.locator("#stage-cards")
    page.locator("#stage-populations button", has_text="(re)Create").first.click()
    _confirm(page)
    expect(cards).to_contain_text("Students: 30")
    expect(page.locator("#toasts")).to_contain_text("Created 30 students.")
    page.locator("#stage-populations button", has_text="(re)Create").nth(1).click()
    _confirm(page)
    expect(cards).to_contain_text("Schools: 5")
    page.get_by_role("button", name="(re)Initialize Interviews").click()
    _confirm(page)
    expect(cards).to_contain_text("Interviews: 150")
    page.get_by_role("button", name="Compute Pre-Interview All").click()
    expect(page.get_by_role("dialog")).to_contain_text("for the 150 interview rows")  # the question states counts
    _confirm(page)
    expect(page.locator("#workflow-steps .step-accent")).to_have_text("Pre-Interview")

    assert Interview.objects.filter(simulation=sim, students_pre_rank_of_school__isnull=False).count() == 150


def test_cancelling_the_dialog_changes_nothing(logged_in_page, live, populated_simulation):
    page = logged_in_page
    page.goto(f"{live}/simulations/{populated_simulation.pk}/")
    page.locator("#stage-populations button", has_text="Delete").first.click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_contain_text("Delete all 20 students?")
    dialog.get_by_role("button", name="Cancel").click()
    expect(dialog).to_be_hidden()
    assert populated_simulation.students.count() == 20


def test_a_server_error_is_reported_instead_of_ignored(logged_in_page, live, populated_simulation):
    page = logged_in_page
    page.goto(f"{live}/simulations/{populated_simulation.pk}/")
    page.route("**/initialize-interviews/", lambda route: route.fulfill(status=500, body="boom"))
    page.get_by_role("button", name="(re)Initialize Interviews").click()
    _confirm(page)
    expect(page.locator("#toasts .alert-error")).to_contain_text("error 500")


def test_dark_mode_toggle_persists(logged_in_page, live):
    page = logged_in_page
    page.emulate_media(color_scheme="light")
    page.goto(f"{live}/simulations/")
    page.get_by_role("button", name="Toggle dark mode").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")


def test_attribute_editor_adds_and_saves_items(logged_in_page, live, simulation):
    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/")
    editor = page.locator("[x-data^=metaEditor]").first
    expect(editor.locator("input[aria-label^='Attribute']")).to_have_count(3)
    editor.locator("input[aria-label^='New attribute']").fill("Class Size")
    editor.locator("input[aria-label^='New attribute']").press("Enter")
    expect(editor.locator("input[aria-label='Attribute 4']")).to_have_value("class_size")  # normalised
    page.get_by_role("button", name="Save configuration").click()
    page.wait_for_load_state()
    saved = simulation.configs.get().applicant_meta_preference
    assert saved == ["program_size", "reputation", "location", "class_size"]
