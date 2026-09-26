"""Production-mode smoke tests (plan step 0.1).

The test settings run the production configuration (DEBUG off), so these tests fail if a page or the implemented
workflow only works in debug mode, as happened with the unconditional debug-toolbar URLs (ENG-1).
"""

import os
import subprocess
import sys

import pytest
from django.conf import settings
from django.urls import reverse

from nrmps.models import Simulation
from nrmps.params import load_params
from nrmps.params_forms import post_data

from .conftest import PASSWORD, SMALL_PARAMS

PUBLIC_PAGES = [
    "nrmps:index",
    "nrmps:contact",
    "nrmps:privacy",
    "nrmps:terms",
    "nrmps:help",
    "nrmps:login",
    "nrmps:signup",
]


def test_runs_in_production_mode():
    """The suite exercises the production settings, not the development ones."""
    assert settings.DEBUG is False
    assert "debug_toolbar" not in settings.INSTALLED_APPS
    assert settings.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SECURE is True
    assert settings.SECURE_HSTS_SECONDS > 0


@pytest.mark.django_db
@pytest.mark.parametrize("name", PUBLIC_PAGES)
def test_public_pages_render(client, name):
    """Every public page renders for an anonymous visitor."""
    assert client.get(reverse(name)).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["nrmps:account", "nrmps:simulation_list", "nrmps:simulation_create"])
def test_private_pages_redirect_anonymous_visitors_to_login(client, name):
    """LoginRequiredMiddleware protects every page that is not explicitly public (ENG-14)."""
    response = client.get(reverse(name))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("nrmps:login"))


@pytest.mark.django_db
def test_admin_login_renders(client):
    """The admin login page renders."""
    assert client.get("/admin/login/").status_code == 200


@pytest.mark.django_db
def test_unknown_url_is_404(client):
    """Unknown URLs give a 404, not a server error."""
    assert client.get("/no-such-page/").status_code == 404


@pytest.mark.django_db
def test_https_redirect_is_on_in_production(client, settings):
    """Plain-HTTP requests are redirected to HTTPS in production; proxied HTTPS requests are not."""
    settings.SECURE_SSL_REDIRECT = True
    assert client.get("/").status_code == 301
    assert client.get("/", headers={"x-forwarded-proto": "https"}).status_code == 200


@pytest.mark.django_db
def test_signup_login_logout(client):
    """A visitor can sign up, log out and log back in."""
    data = {"username": "bob", "email": "bob@example.com", "password1": PASSWORD, "password2": PASSWORD}
    response = client.post(reverse("nrmps:signup"), data)
    assert response.status_code == 302
    assert client.post(reverse("nrmps:logout")).status_code == 302
    response = client.post(reverse("nrmps:login"), {"username": "bob", "password": PASSWORD})
    assert response.status_code == 302


def _body(response) -> bytes:
    """Return the body of a regular or streaming response."""
    return b"".join(response.streaming_content) if response.streaming else response.content


@pytest.mark.django_db
def test_implemented_workflow_end_to_end(auth_client):
    """New simulation, parameters, a run, its pages and downloads work with DEBUG off."""
    client = auth_client
    assert client.get(reverse("nrmps:simulation_list")).status_code == 200

    response = client.post(reverse("nrmps:simulation_create"), {"name": "Smoke", "description": "smoke"})
    assert response.status_code == 302
    sim = Simulation.objects.get(name="Smoke")
    manage = reverse("nrmps:simulation_manage", kwargs={"pk": sim.pk})
    assert client.get(manage).status_code == 200

    assert client.post(manage, post_data(load_params(SMALL_PARAMS)) | {"form_id": "params"}).status_code == 302
    response = client.post(reverse("nrmps:run_start", kwargs={"pk": sim.pk}), headers={"hx-request": "true"})
    assert response.status_code == 200
    run = sim.runs.get()
    assert run.status == "succeeded", run.error
    assert (run.n_applicants, run.n_programs) == (60, 8)

    kwargs = {"pk": sim.pk, "number": run.number}
    for name in ("run_detail", "run_applicants", "run_programs"):
        assert client.get(reverse(f"nrmps:{name}", kwargs=kwargs)).status_code == 200, name
    assert (
        client.get(reverse("nrmps:run_applicants", kwargs=kwargs), {"sort": "fidelity", "order": "desc"}).status_code
        == 200
    )
    assert client.get(reverse("nrmps:run_applicant", kwargs=kwargs | {"index": 1})).status_code == 200
    assert client.get(reverse("nrmps:run_program", kwargs=kwargs | {"index": 1})).status_code == 200
    for name, start in (("applicants.csv", b"name,"), ("programs.csv", b"name,"), ("pairs.csv", b"applicant,")):
        response = client.get(reverse("nrmps:run_download", kwargs=kwargs | {"name": name}))
        assert response.status_code == 200
        assert _body(response).startswith(start)
    response = client.get(reverse("nrmps:run_download", kwargs=kwargs | {"name": "pairs.csv"}))
    assert len(_body(response).splitlines()) == 481

    assert client.post(reverse("nrmps:simulation_delete", kwargs={"pk": sim.pk})).status_code == 302
    assert not Simulation.objects.filter(pk=sim.pk).exists()


def _run_django_setup(code: str | None = None, **overrides: str) -> subprocess.CompletedProcess:
    """Start Django with the real settings module in a subprocess and the given environment overrides.

    Variables are set to empty strings rather than removed, so a developer's .env file cannot fill them in.
    """
    env = dict(os.environ)
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "NRMP_Simulated.settings",
            "DEBUG": "False",
            "SECRET_KEY": "subprocess-test-key-0123456789-abcdefghijklmnopqrstuvwxyz",
            "DATABASE_URL": "sqlite:///:memory:",
            "LOGFIRE_SEND_TO_LOGFIRE": "false",
        }
    )
    env.update(overrides)
    code = code or "print(settings.DATABASES['default'])"
    code = f"import django; django.setup(); from django.conf import settings; {code}"
    return subprocess.run(
        [sys.executable, "-c", code], cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize("missing", ["SECRET_KEY", "DATABASE_URL"])
def test_production_refuses_to_start_without_required_settings(missing):
    """With DEBUG off, a missing SECRET_KEY or DATABASE_URL stops start-up instead of using insecure fallbacks."""
    result = _run_django_setup(**{missing: ""})
    assert result.returncode != 0
    assert f"{missing} must be set" in result.stderr


def test_development_mode_uses_local_fallbacks():
    """With DEBUG on, the development key and the local SQLite database are used."""
    result = _run_django_setup(DEBUG="True", SECRET_KEY="", DATABASE_URL="")
    assert result.returncode == 0, result.stderr
    assert "sqlite3" in result.stdout
