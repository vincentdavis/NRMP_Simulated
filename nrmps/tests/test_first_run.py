"""The first run works with the defaults (plan step 0.2: SIM-2, OPT-1, HELP-2, ENG-18, UX-1, UX-18, CRIT-3)."""

import json

import pytest
from django.forms.models import model_to_dict
from django.urls import reverse

from nrmps.forms import SimulationConfigForm
from nrmps.models import Simulation, SimulationConfig

pytestmark = pytest.mark.django_db


def _form_data(config: SimulationConfig) -> dict:
    """Return POST data for the configuration form built from a configuration instance."""
    data = model_to_dict(config, exclude=["id", "simulation"])
    return {key: json.dumps(value) if isinstance(value, list) else value for key, value in data.items()}


def test_model_defaults_pass_the_model_validators(user):
    """The default configuration satisfies its own validators, so it can always be saved unchanged."""
    sim = Simulation.objects.create(owner=user, name="s")
    SimulationConfig(simulation=sim).full_clean()


def test_model_defaults_pass_the_form():
    """Submitting the configuration form with the defaults is valid."""
    form = SimulationConfigForm(data=_form_data(SimulationConfig()))
    assert form.is_valid(), form.errors.as_json()


@pytest.mark.parametrize(
    ("mean", "stddev", "valid"),
    [
        (0.7, 0.1, True),
        (0.7, 0.45, True),  # below sqrt(0.7 * 0.3) = 0.458
        (0.95, 0.2, True),  # below sqrt(0.95 * 0.05) = 0.218
        (0.95, 0.25, False),  # above that limit: no Beta distribution has it
        (0.5, 0.46, False),  # above the field maximum of 0.45
        (0.0, 0.1, False),  # the mean must be strictly inside (0, 1)
    ],
)
def test_score_stddev_must_be_feasible_for_a_beta_distribution(mean, stddev, valid):
    """Infeasible (mean, SD) pairs are rejected with a clear message instead of being silently clamped."""
    for side in ("applicant", "school"):
        config = SimulationConfig(**{f"{side}_score_mean": mean, f"{side}_score_stddev": stddev})
        form = SimulationConfigForm(data=_form_data(config))
        assert form.is_valid() is valid, (side, form.errors.as_json())


def test_infeasible_stddev_message_states_the_limit():
    """The error says what the largest allowed SD is."""
    form = SimulationConfigForm(
        data=_form_data(SimulationConfig(applicant_score_mean=0.95, applicant_score_stddev=0.3))
    )
    assert not form.is_valid()
    assert "must be below 0.218" in form.errors["applicant_score_stddev"][0]


def test_number_inputs_carry_the_model_limits():
    """HTML inputs get the same min/max as the model validators, and integer fields step by 1."""
    form = SimulationConfigForm()
    assert form.fields["number_of_applicants"].widget.attrs["min"] == 1
    assert form.fields["number_of_applicants"].widget.attrs["step"] == "1"
    assert form.fields["applicant_interview_limit"].widget.attrs["step"] == "1"
    assert form.fields["applicant_score_stddev"].widget.attrs["max"] == 0.45
    assert form.fields["school_capacity_mean"].widget.attrs["min"] == 1


def test_new_simulation_gets_a_configuration_and_description_is_optional(auth_client):
    """Creating a simulation with an empty description works and creates a default configuration."""
    response = auth_client.post(
        reverse("nrmps:simulation_create"), {"name": "First", "description": "", "iterations": 1}
    )
    assert response.status_code == 302
    sim = Simulation.objects.get(name="First")
    assert sim.public is False
    assert sim.configs.count() == 1


def test_first_run_generates_populations_without_touching_the_configuration(auth_client):
    """Right after creating a simulation, generating applicants and programs works with the defaults."""
    auth_client.post(reverse("nrmps:simulation_create"), {"name": "First", "description": "", "iterations": 1})
    sim = Simulation.objects.get(name="First")
    for name in ("simulation_create_students", "simulation_create_schools"):
        response = auth_client.post(reverse(f"nrmps:{name}", kwargs={"pk": sim.pk}), headers={"hx-request": "true"})
        assert response.status_code == 200
    assert sim.students.count() == 200
    assert sim.schools.count() == 10
    assert all(0 <= score <= 1 for score in sim.students.values_list("score", flat=True))


def test_untouched_configuration_form_saves(auth_client):
    """Saving the configuration form exactly as rendered succeeds (it used to fail on two fields)."""
    auth_client.post(reverse("nrmps:simulation_create"), {"name": "First", "description": "", "iterations": 1})
    sim = Simulation.objects.get(name="First")
    manage = reverse("nrmps:simulation_manage", kwargs={"pk": sim.pk})
    data = _form_data(sim.configs.get()) | {"form_id": "config"}
    assert auth_client.post(manage, data).status_code == 302


def test_missing_configuration_is_reported(auth_client, user):
    """A simulation without a configuration (created before this fix) explains what to do instead of doing nothing."""
    sim = Simulation.objects.create(owner=user, name="Legacy")
    url = reverse("nrmps:simulation_create_students", kwargs={"pk": sim.pk})
    response = auth_client.post(url, headers={"hx-request": "true"})
    assert response.status_code == 200
    assert b"no configuration yet" in response.content
    assert sim.students.count() == 0
