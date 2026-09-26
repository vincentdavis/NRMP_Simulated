"""The workflow in a real browser: HTMX runs and uploads, the stepper, dialogs and the Alpine list editors."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from playwright.sync_api import expect

from nrmps.models import PopulationUpload, Simulation

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _confirm(page):
    """Accept the site's confirmation dialog."""
    page.get_by_role("dialog").get_by_role("button", name="Continue").click()


def _stage(page, label: str):
    return page.locator("#pipeline li", has_text=label)


def test_a_new_simulation_runs_from_the_page(logged_in_page, live):
    page = logged_in_page
    page.goto(f"{live}/simulations/new/")
    page.fill("#id_name", "Browser run")
    page.get_by_role("button", name="Create", exact=True).click()
    page.wait_for_url(re.compile(r"/simulations/\d+/$"))
    expect(page.locator("#toasts")).to_contain_text("Simulation created")
    expect(_stage(page, "Pre-interview")).to_contain_text("Ready")

    page.locator("#run-panel").get_by_role("button", name="Run", exact=True).click()
    expect(page.locator("#toasts")).to_contain_text("Run 1 finished.")
    expect(_stage(page, "Population")).to_contain_text("Done")
    expect(_stage(page, "Pre-interview")).to_contain_text("Done")
    page.locator("#run-panel").get_by_role("link", name="Results", exact=True).click()
    expect(page.get_by_role("heading", level=1)).to_contain_text("Run 1")
    assert Simulation.objects.get(name="Browser run").runs.get().status == "succeeded"


def test_changing_noise_makes_only_the_pre_interview_stage_stale(logged_in_page, live, simulation, finished_run):
    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/")
    page.get_by_label("Applicant pre-interview noise").fill("1.1")
    page.locator("#parameters").get_by_role("button", name="Save", exact=True).click()
    expect(page.locator("#toasts")).to_contain_text("Parameters saved.")
    expect(_stage(page, "Population")).to_contain_text("Done")
    expect(_stage(page, "Pre-interview")).to_contain_text("Out of date")
    expect(page.locator("#pipeline")).to_contain_text("Changed since run 1: information (noise).")


def test_list_editor_adds_a_row_and_saves_it(logged_in_page, live, simulation):
    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/")
    editor = page.locator("#list-applicants__attributes")
    expect(editor.locator("tbody tr")).to_have_count(3)
    editor.get_by_role("button", name="Add row").click()
    expect(editor.locator("tbody tr")).to_have_count(4)
    editor.get_by_label("Attribute, new row").fill("step_2")
    expect(editor.get_by_label("Correlation with strength, new row")).to_have_value("0.5")  # schema default
    page.locator("#parameters").get_by_role("button", name="Save", exact=True).click()
    expect(page.locator("#toasts")).to_contain_text("Parameters saved.")
    keys = [a.key for a in Simulation.objects.get(pk=simulation.pk).get_params().applicants.attributes]
    assert keys == ["board_scores", "research", "honors", "step_2"]


def test_uploading_the_sample_file(logged_in_page, live, simulation):
    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/")
    sample = Path(settings.BASE_DIR) / "static" / "samples" / "applicants_sample.csv"
    card = page.locator("#population-applicants")
    card.get_by_label("Applicants CSV file").set_input_files(str(sample))
    card.get_by_role("button", name="Upload CSV").click()
    expect(page.locator("#toasts")).to_contain_text("Loaded 12 applicants from the file.")
    expect(page.locator("#population-applicants")).to_contain_text("applicants_sample.csv")
    assert PopulationUpload.objects.get().rows == 12


def test_cancelling_the_dialog_changes_nothing(logged_in_page, live, simulation):
    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/")
    page.get_by_role("button", name="Delete simulation").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_contain_text("Delete the simulation “Test simulation”")
    dialog.get_by_role("button", name="Cancel").click()
    expect(dialog).to_be_hidden()
    assert Simulation.objects.filter(pk=simulation.pk).exists()


def test_a_server_error_is_reported_instead_of_ignored(logged_in_page, live, simulation):
    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/")
    page.route("**/runs/", lambda route: route.fulfill(status=500, body="boom"))
    page.locator("#run-panel").get_by_role("button", name="Run", exact=True).click()
    expect(page.locator("#toasts .alert-error")).to_contain_text("error 500")


def test_dark_mode_toggle_persists(logged_in_page, live):
    page = logged_in_page
    page.emulate_media(color_scheme="light")
    page.goto(f"{live}/simulations/")
    page.get_by_role("button", name="Toggle dark mode").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")


def test_the_setup_form_previews_edits_syncs_sliders_and_flags_unsaved_changes(logged_in_page, live, simulation):
    """Plan step 4.2: the preview follows the form, sliders follow their inputs, and unsaved edits are flagged."""
    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/")
    indicator = page.locator("[data-dirty-indicator]")
    expect(indicator).to_be_hidden()
    preview = page.locator("#params-preview")
    expect(preview).to_contain_text("Positions per program")

    page.get_by_role("spinbutton", name="Applicants", exact=True).fill("4321")
    expect(preview).to_contain_text("4,321")
    expect(indicator).to_be_visible()

    number = page.get_by_label("Applicant agreement", exact=True)
    slider = number.locator("xpath=following-sibling::input[@type='range']")
    expect(slider).to_have_attribute("aria-hidden", "true")
    number.fill("0.25")
    expect(slider).to_have_value("0.25")
    slider.evaluate("(range) => { range.value = '0.4'; range.dispatchEvent(new Event('input', {bubbles: true})); }")
    expect(number).to_have_value("0.4")

    page.locator("#parameters").get_by_role("button", name="Save", exact=True).click()
    expect(page.locator("#toasts")).to_contain_text("Parameters saved.")
    expect(page.locator("[data-dirty-indicator]")).to_be_hidden()
    params = Simulation.objects.get(pk=simulation.pk).get_params()
    assert (params.market.n_applicants, params.prefs.applicant_pref_correlation) == (4321, 0.4)


def test_a_preset_can_be_applied_after_confirming(logged_in_page, live, simulation):
    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/")
    page.get_by_text("Presets and parameter files").click()
    page.get_by_label("Start again from a preset").select_option("classroom")
    page.get_by_role("button", name="Apply preset", exact=True).click()
    _confirm(page)
    expect(page.locator("#toasts")).to_contain_text("Applied the preset “Small classroom market”")
    assert Simulation.objects.get(pk=simulation.pk).get_params().market.n_applicants == 60


def test_help_popovers_and_the_help_panel_work_by_keyboard(logged_in_page, live, simulation, finished_run):
    """Plan step 4.3: "?" opens its popover (Escape closes it), and Help opens the page's panel."""
    from axe_playwright_python.sync_playwright import Axe

    page = logged_in_page
    page.goto(f"{live}/simulations/{simulation.pk}/runs/1/applicants/")
    button = page.get_by_role("button", name="Help: Strength")
    popover = page.locator("#help-column-applicants-strength")
    expect(popover).to_be_hidden()
    button.focus()
    page.keyboard.press("Enter")
    expect(popover).to_be_visible()
    expect(popover).to_contain_text("Latent strength on the z-scale")
    serious = [v["id"] for v in Axe().run(page).response["violations"] if v["impact"] in {"serious", "critical"}]
    assert serious == []
    page.keyboard.press("Escape")
    expect(popover).to_be_hidden()

    page.get_by_role("button", name="Help", exact=True).click()
    panel = page.get_by_role("dialog", name="The applicants of a run")
    expect(panel).to_be_visible()
    expect(panel).to_contain_text("Ranked first by")
    panel.get_by_role("button", name="Close").click()
    expect(panel).to_be_hidden()


def test_the_demo_runs_and_opens_its_results(logged_in_page, live):
    """Plan step 4.5: Try a demo creates a simulation, runs it and shows the results."""
    page = logged_in_page
    page.goto(f"{live}/")
    page.get_by_role("link", name="Try a demo").click()
    page.get_by_label("Small classroom market").check()
    page.get_by_role("button", name="Run the demo").click()
    page.wait_for_url(re.compile(r"/simulations/\d+/runs/1/$"))
    expect(page.get_by_role("heading", level=1)).to_contain_text("Run 1")
    expect(page.locator("main")).to_contain_text("Checks passed")
    assert Simulation.objects.get(name="Demo: Small classroom market").runs.get().status == "succeeded"
