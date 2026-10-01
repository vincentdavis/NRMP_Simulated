"""Onboarding (plan step 4.5): the landing page, Try a demo, the getting-started checklist and the empty list."""

import re

import pytest
from django.urls import reverse

from nrmps.models import Simulation
from nrmps.presets import preset_params

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def _signup_data(name: str, **extra) -> dict:
    return {"username": name, "email": f"{name}@example.com", "password1": PASSWORD, "password2": PASSWORD} | extra


def test_visitors_are_invited_to_try_the_demo(client):
    body = client.get(reverse("nrmps:index")).content.decode()
    assert f'href="{reverse("nrmps:demo")}">Try a demo</a>' in body
    for text in ("What a run does", "Deferred acceptance", "Questions you can explore", "Read the guide"):
        assert text.lower() in body.lower(), text


def test_signing_up_continues_to_the_demo_and_ignores_foreign_next_urls(client):
    page = client.get(reverse("nrmps:signup"), {"next": "/demo/"}).content.decode()
    assert 'name="next" value="/demo/"' in page
    response = client.post(reverse("nrmps:signup"), _signup_data("dora", next="/demo/"))
    assert response["Location"] == "/demo/"
    client.logout()
    response = client.post(reverse("nrmps:signup"), _signup_data("eve", next="https://evil.example/"))
    assert response["Location"] == reverse("nrmps:simulation_list")


def test_the_landing_page_lists_recent_simulations(auth_client, finished_run, simulation):
    body = auth_client.get(reverse("nrmps:index")).content.decode()
    assert f'href="{reverse("nrmps:demo")}"' in body
    assert "Your recent simulations" in body
    assert simulation.name in body
    rate = finished_run.metrics["outcomes"]["match"]["match_rate"]
    assert f"match rate {rate * 100:.1f}%" in body


def test_the_demo_page_offers_markets(auth_client):
    body = auth_client.get(reverse("nrmps:demo")).content.decode()
    for title in (
        "NRMP-like market",
        "Idealized market",
        "Idealized market with signals",
        "Idealized market, signals first",
        "Noisy market",
        "Noisy applicants, perfect programs",
        "Noisy programs, perfect applicants",
        "Small classroom market",
        "Preference signals",
    ):
        assert title in body
    assert "Run the demo" in body
    assert "Log in to run the demo" not in body
    assert _checked(body) == ["nrmp_like"]
    assert _checked(auth_client.get(reverse("nrmps:demo"), {"preset": "signals"}).content.decode()) == ["signals"]


def test_the_demo_creates_runs_and_opens_a_simulation(auth_client, user):
    response = auth_client.post(reverse("nrmps:demo"), {"preset": "classroom"})
    sim = Simulation.objects.get(owner=user)
    run = sim.runs.get()
    assert response["Location"] == reverse("nrmps:run_detail", kwargs={"pk": sim.pk, "number": run.number})
    assert run.status == "succeeded"
    assert sim.name == "Demo: Small classroom market"
    assert sim.get_params().with_seed(1) == preset_params("classroom", seed=1)


def test_the_idealized_demo_runs_its_preset(auth_client, user):
    auth_client.post(reverse("nrmps:demo"), {"preset": "idealized"})
    sim = Simulation.objects.get(owner=user)
    assert sim.name == "Demo: Idealized market"
    assert sim.runs.get().status == "succeeded"
    assert sim.get_params().with_seed(1) == preset_params("idealized", seed=1)


def test_an_unknown_demo_market_falls_back_to_the_default(auth_client, user):
    auth_client.post(reverse("nrmps:demo"), {"preset": "nonsense"})
    assert Simulation.objects.get(owner=user).name == "Demo: NRMP-like market"


def test_the_demo_respects_quotas(auth_client, user, settings):
    settings.NRMP_MAX_SIMULATIONS = 0
    response = auth_client.post(reverse("nrmps:demo"), follow=True)
    assert not Simulation.objects.filter(owner=user).exists()
    assert "simulations" in response.content.decode().lower()


def _checked(body: str) -> list[str]:
    """Return the demo markets checked on the demo page."""
    return re.findall(r'name="preset" value="(\w+)"[^>]* checked', body)


def test_visitors_see_the_demo_markets_and_log_in_to_run_one(client):
    body = client.get(reverse("nrmps:demo")).content.decode()
    assert "Noisy market" in body
    assert "Log in to run the demo" in body
    assert "Run the demo" not in body
    assert _checked(body) == ["nrmp_like"]
    response = client.post(reverse("nrmps:demo"), {"preset": "noisy"})
    assert response["Location"] == "/login/?next=%2Fdemo%2F%3Fpreset%3Dnoisy"
    assert not Simulation.objects.exists()


def test_a_visitor_comes_back_from_logging_in_to_the_market_they_picked(client, user):
    login = client.post(reverse("nrmps:demo"), {"preset": "noisy"})["Location"]
    response = client.post(login, {"username": user.username, "password": PASSWORD})
    assert response["Location"] == "/demo/?preset=noisy"
    body = client.get(response["Location"]).content.decode()
    assert _checked(body) == ["noisy"]
    assert "Run the demo" in body
    assert not Simulation.objects.exists()


def test_a_visitor_can_sign_up_instead_and_come_back_to_their_market(client):
    response = client.post(reverse("nrmps:demo"), {"preset": "idealized", "account": "new"})
    assert response["Location"] == "/signup/?next=%2Fdemo%2F%3Fpreset%3Didealized"
    assert 'name="next" value="/demo/?preset=idealized"' in client.get(response["Location"]).content.decode()
    response = client.post(reverse("nrmps:signup"), _signup_data("fay", next="/demo/?preset=idealized"))
    assert response["Location"] == "/demo/?preset=idealized"


def test_an_unknown_market_from_a_visitor_falls_back_to_the_default(client):
    response = client.post(reverse("nrmps:demo"), {"preset": "nonsense"})
    assert response["Location"] == "/login/?next=%2Fdemo%2F%3Fpreset%3Dnrmp_like"
    assert _checked(client.get(reverse("nrmps:demo"), {"preset": "nonsense"}).content.decode()) == ["nrmp_like"]


def test_the_login_page_passes_where_to_go_next_on_to_sign_up(client):
    body = client.get(reverse("nrmps:login"), {"next": "/demo/?preset=noisy"}).content.decode()
    assert f'href="{reverse("nrmps:signup")}?next=/demo/%3Fpreset%3Dnoisy"' in body
    body = client.get(reverse("nrmps:login"), {"next": "https://evil.example/"}).content.decode()
    assert f'href="{reverse("nrmps:signup")}"' in body
    assert "evil.example" not in body


def test_the_checklist_guides_a_new_simulation_until_two_runs(auth_client, simulation, user):
    from nrmps.runs import run_now

    url = reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})
    body = auth_client.get(url).content.decode()
    assert "Getting started" in body
    assert body.count("To do:") == 3
    run_now(simulation, user)
    body = auth_client.get(url).content.decode()
    assert body.count("To do:") == 1
    assert reverse("nrmps:run_detail", kwargs={"pk": simulation.pk, "number": 1}) in body
    run_now(simulation, user)
    assert "Getting started" not in auth_client.get(url).content.decode()


def test_an_empty_list_offers_the_demo(auth_client):
    body = auth_client.get(reverse("nrmps:simulation_list")).content.decode()
    assert "No simulations yet" in body
    assert f'action="{reverse("nrmps:demo")}"' in body
