"""Feedback, confirmation and navigation (plan step 1.5: UX-2, ENG-16, UX-20, HELP-7, UX-16, UX-13, UX-23)."""

import json

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _toast(response) -> dict:
    """Return the toast event a step response asks the page to show (HX-Trigger header)."""
    return json.loads(response.headers["HX-Trigger"])["toast"]


def _post(client, sim, name):
    return client.post(reverse(f"nrmps:{name}", kwargs={"pk": sim.pk}), headers={"hx-request": "true"})


def test_successful_step_sends_a_success_toast(auth_client, simulation):
    response = _post(auth_client, simulation, "simulation_create_students")
    assert _toast(response) == {"level": "success", "text": "Created 20 students."}


def test_failed_step_sends_an_error_toast(auth_client, populated_simulation):
    response = _post(auth_client, populated_simulation, "simulation_compute_pre_interview_all")
    assert _toast(response) == {"level": "error", "text": "Initialize the interviews first."}


def test_saving_the_configuration_shows_a_message(auth_client, simulation):
    from django.forms.models import model_to_dict

    manage = reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})
    data = {
        key: json.dumps(value) if isinstance(value, list) else value
        for key, value in model_to_dict(simulation.configs.get(), exclude=["id", "simulation"]).items()
    }
    response = auth_client.post(manage, data | {"form_id": "config"}, follow=True)
    assert "Configuration saved" in response.content.decode()


def test_deleting_a_simulation_shows_a_message(auth_client, simulation):
    response = auth_client.post(reverse("nrmps:simulation_delete", kwargs={"pk": simulation.pk}), follow=True)
    assert "Deleted the simulation “Test simulation”." in response.content.decode()


def test_confirmations_state_what_will_be_deleted(auth_client, populated_simulation):
    from nrmps.simulation_engine import initialize_interview

    initialize_interview(populated_simulation)
    body = auth_client.get(reverse("nrmps:simulation_manage", kwargs={"pk": populated_simulation.pk})).content.decode()
    assert "This replaces the 20 current students and deletes all 80 interview rows" in body
    assert "Delete all 4 schools? This also deletes all 80 interview rows" in body
    assert "with its configuration, 20 students, 4 schools and 80 interview rows? This cannot be undone." in body


def test_step_buttons_show_a_spinner_while_running(auth_client, simulation):
    body = auth_client.get(reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})).content.decode()
    assert body.count("htmx-indicator") >= body.count("hx-post=")


def test_navigation_marks_the_current_section(auth_client, simulation):
    body = auth_client.get(reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})).content.decode()
    assert (
        f'<a class="menu-active" aria-current="page" href="{reverse("nrmps:simulation_list")}">Simulations</a>' in body
    )


def test_anonymous_visitors_do_not_see_the_account_link(client):
    body = client.get(reverse("nrmps:index")).content.decode()
    assert reverse("nrmps:account") not in body


def test_skip_link_and_single_main_landmark(client):
    body = client.get(reverse("nrmps:index")).content.decode()
    assert 'href="#main"' in body
    assert body.count('<main id="main"') == 1


def test_theme_is_not_forced_to_light(client):
    """daisyUI follows the system theme unless the visitor chose one (UX-23)."""
    body = client.get(reverse("nrmps:index")).content.decode()
    assert 'data-theme="light"' not in body
    assert "data-theme-toggle" in body


def test_tables_show_rounded_numbers_and_attribute_chips(auth_client, populated_simulation):
    body = auth_client.get(reverse("nrmps:simulation_students", kwargs={"pk": populated_simulation.pk})).content
    student = populated_simulation.students.order_by("id").first()
    assert f"{student.score:.3f}".encode() in body
    assert repr(student.score).encode() not in body or len(repr(student.score)) <= 5
    assert b"{&#x27;" not in body  # no Python dict reprs
