"""Feedback, confirmation and navigation (plan step 1.5: UX-2, ENG-16, UX-20, HELP-7, UX-16, UX-13, UX-23)."""

import json

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _toast(response) -> dict:
    """Return the toast event an HTMX response asks the page to show (HX-Trigger header)."""
    return json.loads(response.headers["HX-Trigger"])["toast"]


def _run(client, sim):
    return client.post(reverse("nrmps:run_start", kwargs={"pk": sim.pk}), headers={"hx-request": "true"})


def test_successful_run_sends_a_success_toast(auth_client, simulation):
    assert _toast(_run(auth_client, simulation)) == {"level": "success", "text": "Run 1 finished."}


def test_refused_run_sends_an_error_toast(auth_client, simulation, settings):
    settings.NRMP_MAX_PAIRS = 1
    assert _toast(_run(auth_client, simulation))["level"] == "error"


def test_saving_the_parameters_shows_a_message(auth_client, simulation):
    from nrmps.params_forms import post_data

    manage = reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})
    data = post_data(simulation.get_params()) | {"form_id": "params"}
    response = auth_client.post(manage, data, follow=True)
    assert "Parameters saved." in response.content.decode()


def test_deleting_a_simulation_shows_a_message(auth_client, simulation):
    response = auth_client.post(reverse("nrmps:simulation_delete", kwargs={"pk": simulation.pk}), follow=True)
    assert "Deleted the simulation “Test simulation”." in response.content.decode()


def test_confirmations_state_what_will_be_deleted(auth_client, finished_run, simulation):
    body = auth_client.get(reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})).content.decode()
    assert "with its parameters, uploaded files and 1 runs? This cannot be undone." in body
    run_page = auth_client.get(reverse("nrmps:run_detail", kwargs={"pk": simulation.pk, "number": 1})).content
    assert "Delete run 1 and its results?" in run_page.decode()


def test_action_buttons_show_a_spinner_while_running(auth_client, simulation):
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
    assert 'popovertarget="display-settings"' in body
    for value in ("system", "light", "dark"):
        assert f'name="display-theme" value="{value}"' in body
