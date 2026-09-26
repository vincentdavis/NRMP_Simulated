"""The help registry (plan step 4.3): system checks, anchors, "?" popovers and the Help panel of every page."""

import re

import pytest
from django.template import Context, Template
from django.urls import reverse

from nrmps import checks, help_registry
from nrmps.params import SimulationParams, iter_fields
from nrmps.templatetags.help_tags import help_icon, page_help

pytestmark = pytest.mark.django_db


def test_the_registry_passes_its_checks():
    assert checks.check_help() == []


def test_the_checks_find_gaps(monkeypatch):
    monkeypatch.setitem(
        help_registry.PAGES, "broken", help_registry.PageHelp("Broken", "x", actions=("nope",), columns=("no.pe",))
    )
    monkeypatch.setitem(help_registry.ACTIONS, "lost", help_registry.HelpEntry("Lost", "x", "nowhere"))
    found = {message.id for message in checks.check_help()}
    assert found == {"nrmps.H002", "nrmps.H003"}


def test_a_parameter_without_a_description_is_reported(monkeypatch):
    spec = next(iter_fields(SimulationParams))
    blank = type(spec)(**{**spec.__dict__, "description": ""})
    monkeypatch.setattr(
        checks, "iter_fields", lambda model, prefix="": iter([blank] if model is SimulationParams else [])
    )
    assert [message.id for message in checks.check_help()] == ["nrmps.H001"]


def test_every_help_link_and_parameter_anchor_exists_on_the_help_page(client):
    body = client.get(reverse("nrmps:help")).content.decode()
    ids = set(re.findall(r'id="([^"]+)"', body))
    assert set(help_registry.HELP_ANCHORS) <= ids
    for spec in iter_fields(SimulationParams):
        assert help_registry.param_anchor(spec.path) in ids, spec.path


def test_help_icons_need_a_registered_key():
    context = help_icon("column", "applicants.strength")
    assert context["id"] == "help-column-applicants-strength"
    assert help_icon("action", "upload", "programs")["id"] == "help-action-upload-programs"
    with pytest.raises(KeyError):
        help_icon("column", "applicants.nonsense")
    with pytest.raises(KeyError):
        page_help("nonsense")


def test_the_popover_markup_is_accessible():
    html = Template('{% load help_tags %}{% help_icon "action" "run" %}').render(Context())
    assert 'popovertarget="help-action-run"' in html
    assert 'aria-label="Help: Run"' in html
    assert '<div id="help-action-run" popover' in html
    assert "Learn more in the help" in html


@pytest.mark.parametrize(
    ("view", "kwargs_of", "page"),
    [
        ("nrmps:simulation_list", None, "simulation-list"),
        ("nrmps:simulation_create", None, "simulation-create"),
        ("nrmps:simulation_manage", "simulation", "simulation-manage"),
        ("nrmps:run_detail", "run", "run-summary"),
        ("nrmps:run_population", "run", "run-population"),
        ("nrmps:run_pre_interview", "run", "run-pre-interview"),
        ("nrmps:run_applications", "run", "run-applications"),
        ("nrmps:run_match", "run", "run-match"),
        ("nrmps:run_applicants", "run", "run-applicants"),
        ("nrmps:run_programs", "run", "run-programs"),
    ],
)
def test_every_page_has_a_help_panel(auth_client, finished_run, view, kwargs_of, page):
    kwargs = {}
    if kwargs_of == "simulation":
        kwargs = {"pk": finished_run.simulation_id}
    elif kwargs_of == "run":
        kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number}
    body = auth_client.get(reverse(view, kwargs=kwargs)).content.decode()
    assert f'popovertarget="page-help-{page}"' in body
    assert f'aria-labelledby="page-help-{page}-title"' in body


def test_the_agent_page_has_a_help_panel_and_column_help(auth_client, finished_run):
    url = reverse("nrmps:run_applicant", kwargs={"pk": finished_run.simulation_id, "number": 1, "index": 1})
    body = auth_client.get(url).content.decode()
    assert 'popovertarget="page-help-run-agent"' in body
    assert 'popovertarget="help-column-agent-stages-list-rank"' in body


def test_list_columns_and_actions_have_help(auth_client, finished_run, simulation):
    url = reverse("nrmps:run_applicants", kwargs={"pk": simulation.pk, "number": finished_run.number})
    body = auth_client.get(url).content.decode()
    for key in ("strength", "fidelity", "percentile", "match"):
        assert f'popovertarget="help-column-applicants-{key}"' in body, key
    assert 'popovertarget="help-action-download-csv"' in body
    manage = auth_client.get(reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})).content.decode()
    for action in ("run", "save-params", "save-and-run", "apply-preset", "upload-applicants", "upload-programs"):
        assert f'popovertarget="help-action-{action}"' in manage, action


def test_parameter_fields_show_their_range_default_and_a_link(auth_client, simulation):
    body = auth_client.get(reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})).content.decode()
    body = " ".join(body.split())
    assert "Range 0\u20131; default 0.6." in body  # an en dash
    assert f'href="{reverse("nrmps:help")}#param-prefs-applicant_pref_correlation"' in body


def test_popover_elements_have_no_display_class():
    """A display class (card, flex, grid, block) would override the browser's hiding of a closed popover."""
    from pathlib import Path

    from django.conf import settings

    display = {"card", "flex", "grid", "block", "inline", "inline-block", "inline-flex", "table", "contents"}
    for path in Path(settings.BASE_DIR, "templates").rglob("*.html"):
        for classes in re.findall(r"<[a-z]+[^>]*\spopover[\s>][^>]*?class=\"([^\"]*)\"", path.read_text()):
            assert not display & set(classes.split()), (path.name, classes)
        for classes in re.findall(r"<[a-z]+[^>]*class=\"([^\"]*)\"[^>]*\spopover[\s>]", path.read_text()):
            assert not display & set(classes.split()), (path.name, classes)
