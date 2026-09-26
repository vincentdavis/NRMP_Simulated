"""The help registry (plan step 4.3): system checks, anchors, "?" popovers and the Help panel of every page."""

import re

import pytest
from django.template import Context, Template
from django.urls import reverse
from django.utils.html import escape

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


def test_an_incomplete_chart_is_reported(monkeypatch):
    """A chart needs its question, what it shows and how to read it, a known place and a known colour (H004)."""
    monkeypatch.setitem(help_registry.CHARTS, "vague", help_registry.ChartHelp("Vague?", "", "x", tab="nowhere"))
    monkeypatch.setitem(help_registry.CHARTS, "odd", help_registry.ChartHelp("Odd?", "x", "y", tab="agent", side="?"))
    messages = [message for message in checks.check_help() if message.id == "nrmps.H004"]
    assert len(messages) == 3


def test_every_chart_is_described_and_linked_from_the_guide(client):
    body = client.get(reverse("nrmps:help_page", kwargs={"slug": "results"})).content.decode()
    for key, chart in help_registry.CHARTS.items():
        assert str(chart.title).endswith("?"), key  # the caption states the question the chart answers
        assert f'id="{help_registry.chart_anchor(key)}"' in body, key
        assert escape(str(chart.title)) in body


def test_chart_help_popovers_link_to_the_guide():
    html = help_icon("chart", "funnel")
    assert html["entry"].title == help_registry.CHARTS["funnel"].title
    assert html["entry"].more == "results#chart-funnel"
    assert "drop-offs" in html["entry"].text
    with pytest.raises(KeyError):
        help_icon("chart", "no_such_chart")


def test_a_parameter_without_a_description_is_reported(monkeypatch):
    spec = next(iter_fields(SimulationParams))
    blank = type(spec)(**{**spec.__dict__, "description": ""})
    monkeypatch.setattr(
        checks, "iter_fields", lambda model, prefix="": iter([blank] if model is SimulationParams else [])
    )
    assert [message.id for message in checks.check_help()] == ["nrmps.H001"]


def test_every_parameter_has_an_anchor_in_the_reference(client):
    body = client.get(reverse("nrmps:help_page", kwargs={"slug": "parameters"})).content.decode()
    ids = set(re.findall(r'id="([^"]+)"', body))
    for spec in iter_fields(SimulationParams):
        assert help_registry.param_anchor(spec.path) in ids, spec.path


def test_a_link_to_a_missing_guide_section_is_reported(monkeypatch):
    monkeypatch.setitem(help_registry.ACTIONS, "lost", help_registry.HelpEntry("Lost", "x", "model#nowhere"))
    assert [message.id for message in checks.check_help()] == ["nrmps.H003"]


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
    url = reverse("nrmps:help_page", kwargs={"slug": "parameters"})
    assert f'href="{url}#param-prefs-applicant_pref_correlation"' in body


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
