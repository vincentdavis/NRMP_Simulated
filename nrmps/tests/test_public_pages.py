"""Honest public pages and error pages (plan step 0.7: CRIT-5, CRIT-4, UX-17, HELP-14, UX-24, HELP-21)."""

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db

PUBLIC = ["nrmps:index", "nrmps:contact", "nrmps:privacy", "nrmps:terms", "nrmps:login", "nrmps:signup"]


@pytest.mark.parametrize("name", PUBLIC)
def test_every_page_carries_the_non_affiliation_disclaimer(client, name):
    body = client.get(reverse(name)).content.decode()
    assert "Not affiliated with, sponsored or endorsed by the" in body
    assert "National Resident Matching Program&reg;" in body
    assert "not predictions" in body


def test_home_page_quick_start_matches_the_real_flow(client):
    body = client.get(reverse("nrmps:index")).content.decode()
    assert "via the Admin" not in body
    assert reverse("nrmps:signup") in body


def test_home_page_for_a_signed_in_user_links_to_their_simulations(auth_client):
    body = auth_client.get(reverse("nrmps:index")).content.decode()
    assert reverse("nrmps:simulation_list") in body


def test_privacy_page_describes_real_storage_and_processors(client):
    body = client.get(reverse("nrmps:privacy")).content.decode()
    assert "kept in your environment" not in body
    for fact in ("Railway", "Logfire", "not kept as files", "session cookie", "salted hash"):
        assert fact in body


def test_terms_cover_predictions_acceptable_use_and_license(client, settings):
    settings.NRMP_MAX_PAIRS = 250000
    body = client.get(reverse("nrmps:terms")).content.decode()
    for fact in ("not predictions", "real applicant data", "MIT License", "250,000 applicant"):
        assert fact in body


def test_contact_page_links_the_real_issue_tracker(client, settings):
    settings.CONTACT_EMAIL = ""
    body = client.get(reverse("nrmps:contact")).content.decode()
    assert "https://github.com/vincentdavis/NRMP_Simulated/issues" in body
    assert "example.com" not in body
    assert "mailto:" not in body


def test_contact_email_is_shown_when_configured(client, settings):
    settings.CONTACT_EMAIL = "help@nrmp-sim.test"
    assert "mailto:help@nrmp-sim.test" in client.get(reverse("nrmps:contact")).content.decode()


def test_404_page_is_friendly(client):
    response = client.get("/no-such-page/")
    assert response.status_code == 404
    assert b"Page not found" in response.content


def test_expired_form_gets_a_helpful_page():
    client = Client(enforce_csrf_checks=True)
    response = client.post(reverse("nrmps:login"), {"username": "x", "password": "y"})
    assert response.status_code == 403
    assert b"This form has expired" in response.content


def test_unknown_host_is_a_friendly_400(client):
    response = client.get("/", headers={"host": "evil.example"})
    assert response.status_code == 400
    assert b"Bad request" in response.content
