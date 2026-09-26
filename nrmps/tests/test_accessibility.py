"""Accessibility checks that need no browser (plan step 1.4: HELP-1, UX-19)."""

import re

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

ID = re.compile(r'\sid="([^"]+)"')
DESCRIBED_BY = re.compile(r'aria-describedby="([^"]+)"')
LABELLED_BY = re.compile(r'aria-labelledby="([^"]+)"')


def _dangling_references(html: str) -> list[str]:
    ids = set(ID.findall(html))
    refs = [ref for value in DESCRIBED_BY.findall(html) + LABELLED_BY.findall(html) for ref in value.split()]
    return [ref for ref in refs if ref not in ids]


def _pages(client, simulation):
    return {
        "manage": reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk}),
        "create": reverse("nrmps:simulation_create"),
        "password": reverse("nrmps:password_change"),
    }


def test_aria_references_resolve_on_form_pages(auth_client, simulation):
    for name, url in _pages(auth_client, simulation).items():
        html = auth_client.get(url).content.decode()
        assert _dangling_references(html) == [], name


def test_aria_references_resolve_when_forms_show_errors(auth_client, simulation):
    """With errors, Django also points aria-describedby at "<id>_error"; those elements must exist too."""
    manage = reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})
    html = auth_client.post(manage, {"form_id": "config", "number_of_applicants": "-1"}).content.decode()
    assert "The configuration was not saved" in html
    assert _dangling_references(html) == []
    html = auth_client.post(reverse("nrmps:simulation_create"), {"name": "", "iterations": 500}).content.decode()
    assert _dangling_references(html) == []


def test_public_form_pages_show_help_and_resolve_references(client):
    for name in ("nrmps:signup", "nrmps:login"):
        html = client.get(reverse(name)).content.decode()
        assert _dangling_references(html) == [], name
    signup = client.get(reverse("nrmps:signup")).content.decode()
    assert "Your password must contain at least 8 characters" in signup  # the password rules are shown (HELP-1)


def test_every_form_control_has_a_label(auth_client, simulation):
    """Every visible input, select and textarea is labelled (for=, aria-label or an :aria-label binding)."""
    manage = reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})
    html = auth_client.get(manage).content.decode()
    label_for = set(re.findall(r'<label[^>]*\sfor="([^"]+)"', html))
    for control in re.findall(r"<(?:input|select|textarea)\b[^>]*>", html):
        if re.search(r'type="(hidden|submit)"', control):
            continue
        control_id = re.search(r'\sid="([^"]+)"', control)
        labelled = (
            (control_id and control_id.group(1) in label_for)
            or "aria-label=" in control
            or ":aria-label=" in control
            or "aria-labelledby=" in control
        )
        assert labelled, control
