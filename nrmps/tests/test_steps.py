"""Step views: errors in cards, fresh cards after every step, bounded pages and streamed exports (steps 0.3/0.4)."""

import json

import pytest
from django.urls import reverse

from nrmps.forms import SimulationConfigForm
from nrmps.models import Interview, SimulationConfig

pytestmark = pytest.mark.django_db


def _post_step(client, sim, name):
    """POST a step action as HTMX and return the response."""
    return client.post(reverse(f"nrmps:{name}", kwargs={"pk": sim.pk}), headers={"hx-request": "true"})


def test_step_response_refreshes_every_card_and_the_stepper(auth_client, populated_simulation):
    """A step returns all stage cards and an out-of-band stepper, so no panel goes stale (UX-5)."""
    response = _post_step(auth_client, populated_simulation, "simulation_initialize_interviews")
    body = response.content.decode()
    assert response.status_code == 200
    assert body.count('id="stage-cards"') == 1
    for card in ("stage-populations", "stage-initialize", "stage-pre_interview", "stage-post_interview"):
        assert f'id="{card}"' in body
    assert body.count('id="workflow-steps"') == 1
    assert 'hx-swap-oob="outerHTML"' in body
    assert "<html" not in body


def test_recreating_applicants_updates_the_interview_card(auth_client, populated_simulation):
    """After a cascade delete the interview count shown is the real one (0), not the old one."""
    _post_step(auth_client, populated_simulation, "simulation_initialize_interviews")
    body = _post_step(auth_client, populated_simulation, "simulation_create_students").content.decode()
    assert "<strong>Interviews:</strong> 0" in body


def test_step_error_is_shown_in_its_card_with_status_200(auth_client, populated_simulation):
    """A problem the user can fix is shown in the card instead of an invisible 500 (SIM-4, ENG-16)."""
    response = _post_step(auth_client, populated_simulation, "simulation_compute_pre_interview_all")
    assert response.status_code == 200
    assert b"Initialize the interviews first" in response.content


def test_attribute_mismatch_is_shown_not_a_server_error(auth_client, populated_simulation):
    _post_step(auth_client, populated_simulation, "simulation_initialize_interviews")
    populated_simulation.schools.update(score_meta={"program_size": 0.5})
    response = _post_step(auth_client, populated_simulation, "simulation_compute_pre_interview_all")
    assert response.status_code == 200
    assert b"regenerate both populations" in response.content
    assert not Interview.objects.filter(student_pre_observed_score_of_school__isnull=False).exists()


def test_post_interview_step_explains_why_it_cannot_run(auth_client, populated_simulation):
    _post_step(auth_client, populated_simulation, "simulation_initialize_interviews")
    _post_step(auth_client, populated_simulation, "simulation_compute_pre_interview_all")
    response = _post_step(auth_client, populated_simulation, "simulation_compute_post_interview_all")
    assert b"No interviews have taken place yet" in response.content
    populated_simulation.refresh_from_db()
    assert populated_simulation.status == "pre_interview"


def test_step_buttons_disable_themselves_and_are_synchronised(auth_client, populated_simulation):
    """Every step control disables itself while running and joins one sync group (CRIT-1, ENG-16)."""
    manage = auth_client.get(reverse("nrmps:simulation_manage", kwargs={"pk": populated_simulation.pk}))
    body = manage.content.decode()
    posts = body.count("hx-post=")
    assert posts > 0
    assert body.count("hx-disabled-elt=") == posts
    assert body.count('hx-sync="#stage-cards:drop"') == posts


def test_non_owner_cannot_run_steps(client, other_user, populated_simulation):
    client.force_login(other_user)
    for name in (
        "simulation_create_students",
        "simulation_initialize_interviews",
        "simulation_compute_pre_interview_all",
    ):
        assert _post_step(client, populated_simulation, name).status_code == 404


def test_config_form_rejects_markets_above_the_size_limit(settings):
    settings.NRMP_MAX_PAIRS = 1000
    data = {
        key: json.dumps(value) if isinstance(value, list) else value
        for key, value in SimulationConfig(number_of_applicants=200, number_of_schools=10).__dict__.items()
        if not key.startswith("_") and key not in {"id", "simulation_id"}
    }
    form = SimulationConfigForm(data=data)
    assert not form.is_valid()
    assert "above the current limit of 1,000 pairs" in form.errors["number_of_applicants"][0]


@pytest.mark.parametrize("name", ["simulation_students", "simulation_schools", "simulation_interviews"])
@pytest.mark.parametrize(("requested", "used"), [("100000000", 100), ("-5", 100), ("abc", 100), ("25", 25)])
def test_page_size_is_limited_to_the_offered_sizes(auth_client, populated_simulation, name, requested, used):
    """An arbitrary page_size cannot make a list page load the whole table (ENG-5)."""
    url = reverse(f"nrmps:{name}", kwargs={"pk": populated_simulation.pk})
    response = auth_client.get(url, {"page_size": requested})
    assert response.status_code == 200
    assert response.context["page_size"] == used


@pytest.mark.parametrize(
    ("name", "lines"),
    [("simulation_download_students", 21), ("simulation_download_schools", 5), ("simulation_download_interviews", 81)],
)
def test_csv_exports_stream(auth_client, populated_simulation, name, lines):
    """Exports are generated row by row instead of being built in memory (ENG-5)."""
    from nrmps.simulation_engine import initialize_interview

    initialize_interview(populated_simulation)
    response = auth_client.get(reverse(f"nrmps:{name}", kwargs={"pk": populated_simulation.pk}))
    assert response.streaming
    body = b"".join(response.streaming_content).decode()
    assert len(body.splitlines()) == lines


def _button_disabled(body: str, label: str) -> bool:
    """Return whether the step button with this label is rendered disabled."""
    import re

    match = re.search(r"<button[^>]*>\s*" + re.escape(label) + r"\s*</button>", body, re.S)
    assert match, label
    return re.search(r"\sdisabled[\s>]", match.group(0)) is not None


@pytest.mark.parametrize(
    ("status", "initialize", "pre_interview", "post_interview"),
    [
        ("setup", False, False, False),
        ("populations", True, False, False),
        ("initialized", True, True, False),
        ("pre_interview", True, True, False),
    ],
)
def test_next_step_button_is_enabled_once_its_prerequisite_is_reached(
    auth_client, simulation, status, initialize, pre_interview, post_interview
):
    """Each step can be started from the page as soon as the stage it needs is reached (L-4).

    The buttons used to stay disabled until their own stage had been reached, so after generating populations the
    "Initialize Interviews" button could never be clicked.
    """
    simulation.set_stage(status)
    body = auth_client.get(reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})).content.decode()
    assert _button_disabled(body, "(re)Initialize Interviews") is not initialize
    assert _button_disabled(body, "Compute Pre-Interview All") is not pre_interview
    assert _button_disabled(body, "Compute Post-Interview All") is not post_interview
