"""The help guide and the developer reference (plan steps 1.10 and 2.3: HELP-5, UX-12, HELP-22, CRIT-15)."""

import pytest
from django.urls import reverse

from nrmps.engine import MODEL_VERSION

pytestmark = pytest.mark.django_db


def test_help_page_is_public_and_generated_from_the_schema(client):
    body = " ".join(client.get(reverse("nrmps:help")).content.decode().split())
    for text in (
        "Quick start",
        "How the simulation works",
        f"model {MODEL_VERSION}",
        "1,000 applicants for 926 positions in 142 programs",
        "Applicant agreement",
        "Mean positions per program",
        "Applicant groups",
        "Correlation with strength",
        "samples/applicants_sample.csv",
        "name,group,strength,board_scores,research,honors,weight:reputation,weight:program_size,weight:location",
        "name,tier,quality,capacity,reputation,location",
    ):
        assert text in body, text
    assert "Not used yet" in body  # planned parameters are marked


def test_old_documentation_url_redirects_to_help(client):
    response = client.get("/documentation/")
    assert response.status_code == 301
    assert response["Location"] == reverse("nrmps:help")


def test_developer_reference_is_for_staff_only(client, auth_client, django_user_model):
    url = reverse("nrmps:developer_reference")
    assert client.get(url).status_code == 302
    assert auth_client.get(url).status_code == 302
    staff = django_user_model.objects.create_user("staff", email="staff@example.com", password="x", is_staff=True)
    client.force_login(staff)
    body = client.get(url).content.decode()
    for text in ("engine.pipeline.run_pre_interview", "runs.start_run", "SimulationRun", "engine.rng.philox4x32"):
        assert text in body, text
    assert "check_password" not in body  # no inherited auth internals
    assert "set_password" not in body


def test_navigation_links_to_help(client):
    assert reverse("nrmps:help") in client.get(reverse("nrmps:index")).content.decode()
