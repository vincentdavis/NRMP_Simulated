"""Honest public pages and error pages (plan step 0.7: CRIT-5, CRIT-4, UX-17, HELP-14, UX-24, HELP-21)."""

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db

PUBLIC = [
    "nrmps:index",
    "nrmps:contact",
    "nrmps:privacy",
    "nrmps:terms",
    "nrmps:login",
    "nrmps:signup",
    "nrmps:examples",
]


def _text(response) -> str:
    """Return the response body with runs of whitespace collapsed, as a browser would show it."""
    return " ".join(response.content.decode().split())


@pytest.mark.parametrize("name", PUBLIC)
def test_every_page_carries_the_non_affiliation_disclaimer(client, name):
    body = _text(client.get(reverse(name)))
    assert "Not affiliated with, sponsored or endorsed by the" in body
    assert "National Resident Matching Program&reg;" in body
    assert "not predictions" in body


# What visitors, link checkers and monitors may ask for with HEAD: the headers of a GET, without the page.
HEAD = [
    "/",
    "/demo/",
    "/examples/",
    "/examples/small-classroom-market/",
    "/examples/small-classroom-market/match/",
    "/examples/small-classroom-market/applicants/1/",
    "/help/",
    "/help/model/",
    "/help/search/?q=match",
    "/contact/",
    "/privacy/",
    "/terms/",
    "/login/",
    "/signup/",
    "/robots.txt",
    "/sitemap.xml",
    "/healthz",
]


@pytest.mark.parametrize("path", HEAD)
def test_public_pages_answer_head_requests(client, path):
    get, head = client.get(path), client.head(path)
    assert head.status_code == get.status_code == 200
    assert head.content == b""
    assert get.content
    assert head["Content-Type"] == get["Content-Type"]


def test_head_requests_follow_redirects_and_other_methods_stay_refused(client, django_user_model):
    assert client.head("/favicon.ico").status_code == 301
    assert client.head("/documentation/").status_code in {301, 302}
    assert client.head("/simulations/").status_code == 302  # to the login page, as a GET
    for path in ("/", "/examples/", "/examples/small-classroom-market/", "/help/", "/robots.txt"):
        assert client.put(path).status_code == 405, path
        assert client.delete(path).status_code == 405, path
    assert client.post("/examples/").status_code == 405
    # An example's files are computed when asked for, so only a GET gets them.
    assert client.head("/examples/small-classroom-market/download/match.csv").status_code == 405
    # A HEAD of the forms changes nothing: no simulation, no account.
    assert client.head("/demo/?preset=classroom").status_code == 200
    assert client.head("/signup/").status_code == 200
    assert not django_user_model.objects.exists()


def test_home_page_quick_start_matches_the_real_flow(client):
    body = client.get(reverse("nrmps:index")).content.decode()
    assert "via the Admin" not in body
    assert reverse("nrmps:signup") in body


def test_home_page_for_a_signed_in_user_links_to_their_simulations(auth_client):
    body = auth_client.get(reverse("nrmps:index")).content.decode()
    assert reverse("nrmps:simulation_list") in body


def test_privacy_page_describes_real_storage_and_processors(client):
    body = _text(client.get(reverse("nrmps:privacy")))
    assert "kept in your environment" not in body
    for fact in ("Railway", "Logfire", "not kept as files", "session cookie", "salted hash"):
        assert fact in body


def test_terms_cover_predictions_acceptable_use_and_license(client, settings):
    settings.NRMP_MAX_PAIRS = 250000
    body = _text(client.get(reverse("nrmps:terms")))
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
