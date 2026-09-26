"""The attribute-list editor cannot inject markup (plan step 0.5: UX-10, ENG-7)."""

import html
import json
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict
from django.urls import reverse

from nrmps.models import SimulationConfig
from nrmps.validators import validate_attribute_list

PAYLOAD = 'x"><img src=x onerror=alert(document.domain)>'


@pytest.mark.parametrize(
    "value",
    [
        [],
        "board_scores",
        {"board_scores": 1},
        ["Board Scores"],
        ["board-scores"],
        ["a" * 41],
        ["dup", "dup"],
        [f"a{i}" for i in range(11)],
        ["ok", PAYLOAD],
        ["ok", 3],
    ],
)
def test_invalid_attribute_lists_are_rejected(value):
    with pytest.raises(ValidationError):
        validate_attribute_list(value)


@pytest.mark.parametrize("value", [["board_scores"], ["a", "b_2", "c3"], [f"a{i}" for i in range(10)], ["a" * 40]])
def test_valid_attribute_lists_pass(value):
    validate_attribute_list(value)


def _config_data(config: SimulationConfig, **overrides) -> dict:
    data = model_to_dict(config, exclude=["id", "simulation"]) | overrides
    return {key: json.dumps(value) if isinstance(value, list) else value for key, value in data.items()} | {
        "form_id": "config"
    }


@pytest.mark.django_db
def test_markup_in_an_attribute_name_is_rejected_not_stored(auth_client, simulation):
    """A direct POST that bypasses the browser editor cannot store markup."""
    manage = reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})
    config = simulation.configs.get()
    response = auth_client.post(manage, _config_data(config, applicant_meta_preference=["ok", PAYLOAD]))
    assert response.status_code == 200  # re-rendered with errors
    config.refresh_from_db()
    assert PAYLOAD not in config.applicant_meta_preference
    assert "<img src=x onerror" not in response.content.decode()


@pytest.mark.django_db
def test_stored_markup_from_old_data_is_escaped(auth_client, simulation):
    """Even a payload already in the database (saved before validation existed) renders inert."""
    SimulationConfig.objects.filter(simulation=simulation).update(applicant_meta_preference=["ok", PAYLOAD])
    body = auth_client.get(reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})).content.decode()
    assert "<img src=x onerror" not in body
    assert 'x-init="alert' not in body


@pytest.mark.django_db
def test_page_works_without_javascript(auth_client, simulation):
    """The hidden inputs carry valid JSON, so submitting the form as rendered (no Alpine) keeps the lists."""
    manage = reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})
    body = auth_client.get(manage).content.decode()
    config = simulation.configs.get()
    data = _config_data(config)
    for side in ("applicant", "school"):
        match = re.search(
            rf'name="{side}_meta_preference" id="id_{side}_meta_preference"\s+:value="jsonValue\(\)" value="([^"]*)"',
            body,
        )
        assert match, side
        data[f"{side}_meta_preference"] = html.unescape(match.group(1))
    assert auth_client.post(manage, data).status_code == 302
    config.refresh_from_db()
    assert config.applicant_meta_preference == ["program_size", "reputation", "location"]


def test_templates_never_mark_content_safe():
    """`|safe` and `{% autoescape off %}` are banned in templates (ENG-7)."""
    roots = [Path(d) for d in settings.TEMPLATES[0]["DIRS"]]
    offenders = [
        str(path)
        for root in roots
        for path in root.rglob("*.html")
        if "|safe" in (text := path.read_text()) or "autoescape off" in text
    ]
    assert offenders == []
