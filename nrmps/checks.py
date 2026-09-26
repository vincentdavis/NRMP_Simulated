"""System checks of the help (plan step 4.3): run at start-up and by `manage.py check`, so gaps fail CI.

- nrmps.H001: a parameter of the schema (or a column of a list parameter) has no title or description.
- nrmps.H002: a page's Help panel names an action or column the registry does not describe.
- nrmps.H003: a help entry links to a guide page (or a section of one) that does not exist.
- nrmps.H004: a chart of the catalog lacks its question, what it shows or how to read it, or names an unknown place
  or colour.
"""

from typing import Any

from django.core.checks import CheckMessage, Error, register

from . import help_registry
from .guide import help_url_parts, render_page
from .params import SimulationParams, iter_fields, list_fields


def _parameter_problems() -> list[CheckMessage]:
    specs = [*iter_fields(SimulationParams)]
    for path, _field, item in list_fields(SimulationParams):
        specs += [*iter_fields(item, prefix=f"{path}[].")]
    return [
        Error(f"The parameter {spec.path} has no title or description.", id="nrmps.H001", obj=spec.path)
        for spec in specs
        if not spec.title or not spec.description
    ]


def _page_problems() -> list[CheckMessage]:
    problems: list[CheckMessage] = []
    for key, page in help_registry.PAGES.items():
        problems += [
            Error(f"Page help {key!r} names the unknown action {name!r}.", id="nrmps.H002")
            for name in page.actions
            if name not in help_registry.ACTIONS
        ]
        problems += [
            Error(f"Page help {key!r} names the unknown column {name!r}.", id="nrmps.H002")
            for name in page.columns
            if name not in help_registry.COLUMNS
        ]
    return problems


def _chart_problems() -> list[CheckMessage]:
    problems: list[CheckMessage] = []
    for key, chart in help_registry.CHARTS.items():
        if not chart.title or not chart.what or not chart.how:
            message = f"Chart {key!r} needs a question, what it shows and how to read it."
            problems.append(Error(message, id="nrmps.H004"))
        if chart.tab not in help_registry.CHART_PLACES:
            problems.append(Error(f"Chart {key!r} names the unknown place {chart.tab!r}.", id="nrmps.H004"))
        if chart.side not in {"applicant", "program"}:
            problems.append(Error(f"Chart {key!r} names the unknown colour {chart.side!r}.", id="nrmps.H004"))
    return problems


def _target_exists(target: str) -> bool:
    slug, anchor = help_url_parts(target)
    try:
        page = render_page(slug)
    except KeyError:
        return False
    return not anchor or anchor in page.ids


def _link_problems() -> list[CheckMessage]:
    links = [
        *((key, entry.more) for key, entry in help_registry.ACTIONS.items()),
        *((key, entry.more) for key, entry in help_registry.COLUMNS.items()),
        *((key, page.more) for key, page in help_registry.PAGES.items()),
        *((key, help_registry.chart_target(key)) for key in help_registry.CHARTS),
    ]
    return [
        Error(f"Help entry {key!r} links to the missing help target {target!r}.", id="nrmps.H003")
        for key, target in links
        if target and not _target_exists(target)
    ]


@register("nrmps")
def check_help(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """Return the help registry's problems (none when everything is described and every link resolves)."""
    return _parameter_problems() + _page_problems() + _chart_problems() + _link_problems()
