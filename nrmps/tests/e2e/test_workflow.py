"""The workflow runs in a real browser: HTMX step buttons, confirm dialogs and the Alpine tag editor."""

import re

import pytest
from playwright.sync_api import expect

from nrmps.models import Interview, Simulation

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_steps_run_from_the_page(logged_in_page, live):
    page = logged_in_page
    page.on("dialog", lambda dialog: dialog.accept())  # hx-confirm prompts

    page.goto(f"{live}/simulations/new/")
    page.fill("#id_name", "Browser run")
    page.get_by_role("button", name="Create", exact=True).click()
    page.wait_for_url(re.compile(r"/simulations/\d+/$"))
    sim = Simulation.objects.get(name="Browser run")

    # Make the market small so the steps are quick, through the real configuration form.
    page.fill("#id_number_of_applicants", "30")
    page.fill("#id_number_of_schools", "5")
    page.get_by_role("button", name="Save configuration").click()
    page.wait_for_load_state()

    cards = page.locator("#stage-cards")
    page.locator("#stage-populations button", has_text="(re)Create").first.click()
    expect(cards).to_contain_text("Students: 30")
    page.locator("#stage-populations button", has_text="(re)Create").nth(1).click()
    expect(cards).to_contain_text("Schools: 5")
    page.get_by_role("button", name="(re)Initialize Interviews").click()
    expect(cards).to_contain_text("Interviews: 150")
    page.get_by_role("button", name="Compute Pre-Interview All").click()
    expect(page.locator("#workflow-steps .step-accent")).to_have_text("Pre-Interview")

    assert Interview.objects.filter(simulation=sim, students_pre_rank_of_school__isnull=False).count() == 150


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
    simulation.configs.get().refresh_from_db()
    assert simulation.configs.get().applicant_meta_preference == ["program_size", "reputation", "location", "class_size"]
