"""The help guide and the developer reference (plan step 1.10: HELP-5, UX-12, HELP-22, CRIT-15)."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_help_page_is_public_and_generated_from_the_forms(client):
    body = " ".join(client.get(reverse("nrmps:help")).content.decode().split())
    for text in (
        "Quick start",
        "How the simulation works",
        "Applicant score SD",
        "Positions per program (mean)",
        "samples/applicants_sample.csv",
        "name,capacity,score,score_meta,meta_preference",
    ):
        assert text in body
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
    assert "compute_pre_interview_scores_and_rankings" in body
    assert "check_password" not in body  # no inherited auth internals
    assert "set_password" not in body


def test_navigation_links_to_help(client):
    assert reverse("nrmps:help") in client.get(reverse("nrmps:index")).content.decode()
