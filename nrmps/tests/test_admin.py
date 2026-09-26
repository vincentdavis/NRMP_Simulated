"""The admin site lists and shows every model (plan steps 1.8 and 2.3, ENG-19)."""

import pytest
from django.urls import reverse

from nrmps.models import PopulationUpload

pytestmark = pytest.mark.django_db

MODELS = ["user", "simulation", "simulationrun", "runartifact", "populationupload"]


@pytest.fixture
def staff_client(client, django_user_model):
    admin = django_user_model.objects.create_superuser("root", "root@example.com", "Admin-Pass-123!")
    client.force_login(admin)
    return client


@pytest.fixture
def upload(simulation):
    return PopulationUpload.objects.create(
        simulation=simulation, side="applicants", filename="a.csv", rows=1, data=b"npz", digest="d"
    )


@pytest.mark.parametrize("model", MODELS)
def test_changelists_render(staff_client, finished_run, upload, model):
    response = staff_client.get(reverse(f"admin:nrmps_{model}_changelist"))
    assert response.status_code == 200


def test_simulation_change_page_shows_its_parameters(staff_client, simulation):
    response = staff_client.get(reverse("admin:nrmps_simulation_change", args=[simulation.pk]))
    assert response.status_code == 200
    assert b"n_applicants" in response.content


def test_runs_cannot_be_edited_and_show_their_stages(staff_client, finished_run):
    assert staff_client.get(reverse("admin:nrmps_simulationrun_add")).status_code == 403
    change = staff_client.get(reverse("admin:nrmps_simulationrun_change", args=[finished_run.pk]))
    assert change.status_code == 200
    assert b'name="_save"' not in change.content  # view-only
    assert b"pre_interview" in change.content


def test_artifact_bytes_are_not_shown(staff_client, finished_run):
    artifact = finished_run.artifacts.first()
    change = staff_client.get(reverse("admin:nrmps_runartifact_change", args=[artifact.pk]))
    assert change.status_code == 200
    assert b"PK\x03\x04" not in change.content


def test_regular_users_cannot_use_the_admin(auth_client):
    response = auth_client.get(reverse("admin:index"))
    assert response.status_code == 302
