"""The admin site lists and shows every model (plan step 1.8, ENG-19)."""

import pytest
from django.urls import reverse

from nrmps import simulation_engine as se

pytestmark = pytest.mark.django_db

MODELS = ["user", "simulation", "simulationconfig", "student", "school", "interview", "match"]


@pytest.fixture
def staff_client(client, django_user_model):
    admin = django_user_model.objects.create_superuser("root", "root@example.com", "Admin-Pass-123!")
    client.force_login(admin)
    return client


@pytest.mark.parametrize("model", MODELS)
def test_changelists_render(staff_client, populated_simulation, model):
    se.initialize_interview(populated_simulation)
    response = staff_client.get(reverse(f"admin:nrmps_{model}_changelist"))
    assert response.status_code == 200


def test_simulation_change_page_shows_its_configuration(staff_client, simulation):
    response = staff_client.get(reverse("admin:nrmps_simulation_change", args=[simulation.pk]))
    assert response.status_code == 200
    assert b"number_of_applicants" in response.content


def test_generated_rows_cannot_be_edited(staff_client, populated_simulation):
    student = populated_simulation.students.first()
    assert staff_client.get(reverse("admin:nrmps_student_add")).status_code == 403
    change = staff_client.get(reverse("admin:nrmps_student_change", args=[student.pk]))
    assert change.status_code == 200
    assert b'name="_save"' not in change.content  # view-only


def test_regular_users_cannot_use_the_admin(auth_client):
    response = auth_client.get(reverse("admin:index"))
    assert response.status_code == 302
