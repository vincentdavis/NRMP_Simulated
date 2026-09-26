"""System checks of the help (plan step 4.3): run at start-up and by `manage.py check`, so gaps fail CI.

- nrmps.H001: a parameter of the schema (or a column of a list parameter) has no title or description.
- nrmps.H002: a page's Help panel names an action or column the registry does not describe.
- nrmps.H003: a help entry links to a guide page (or a section of one) that does not exist.
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
    ]
    return [
        Error(f"Help entry {key!r} links to the missing help target {target!r}.", id="nrmps.H003")
        for key, target in links
        if target and not _target_exists(target)
    ]


@register("nrmps")
def check_help(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """Return the help registry's problems (none when everything is described and every link resolves)."""
    return _parameter_problems() + _page_problems() + _link_problems()
