"""Deployment and operations (plan step 1.2: ENG-10, ENG-11, CRIT-11)."""

from unittest import mock

import pytest
from django.db import DatabaseError
from django.urls import reverse

from .test_smoke import _run_django_setup

pytestmark = pytest.mark.django_db


def test_health_check_reports_ok_without_login(client):
    response = client.get(reverse("nrmps:healthz"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_fails_when_the_database_is_down(client):
    with mock.patch("nrmps.views.connection.cursor", side_effect=DatabaseError("down")):
        response = client.get(reverse("nrmps:healthz"))
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"


def test_health_check_is_not_redirected_to_https(client, settings):
    """Railway's health check calls plain HTTP inside its network; it must not get a redirect."""
    settings.SECURE_SSL_REDIRECT = True
    assert client.get("/healthz").status_code == 200
    assert client.get("/").status_code == 301


def _settings_value(expression: str, **env: str) -> str:
    """Evaluate a settings expression in a fresh process with production settings and the given environment."""
    result = _run_django_setup(code=f"print({expression})", **env)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_railway_health_check_host_is_allowed_on_railway():
    hosts = _settings_value("settings.ALLOWED_HOSTS", RAILWAY_ENVIRONMENT_NAME="production")
    assert "healthcheck.railway.app" in hosts


def test_production_serves_compressed_hashed_static_files():
    backend = _settings_value("settings.STORAGES['staticfiles']['BACKEND']")
    assert backend == "whitenoise.storage.CompressedManifestStaticFilesStorage"


def test_production_reuses_database_connections():
    assert _settings_value("settings.DATABASES['default']['CONN_MAX_AGE']") == "600"
