"""Template tags of the help registry (plan step 4.3): "?" popovers and the Help panel of a page."""

from typing import Any

from django import template

from nrmps import help_registry

register = template.Library()


def _id(*parts: str) -> str:
    return "-".join(part.replace(".", "-").replace("_", "-") for part in parts)


@register.inclusion_tag("nrmps/components/help_popover.html")
def help_icon(kind: str, key: str, suffix: str = "") -> dict[str, Any]:
    """Render the "?" button and popover of a column, an action or a chart.

    `kind` is "column" ("table.column" keys), "action" or "chart" (keys of the chart catalog). `suffix` keeps the
    ids unique when the same help appears more than once on a page. Raises KeyError for a key the registry does not
    describe, so a page that uses one fails its tests.
    """
    if kind == "chart":
        chart = help_registry.chart(key)
        entry = help_registry.HelpEntry(chart.title, chart.text, help_registry.chart_target(key))
    elif kind == "column":
        entry = help_registry.column(key)
    else:
        entry = help_registry.action(key)
    return {"entry": entry, "id": _id("help", kind, key, *([suffix] if suffix else []))}


@register.inclusion_tag("nrmps/components/page_help.html")
def page_help(key: str) -> dict[str, Any]:
    """Render the Help button of a page and its panel: what the page is, what to do next, buttons and columns."""
    page = help_registry.PAGES[key]
    return {
        "page": page,
        "id": _id("page-help", key),
        "actions": [help_registry.ACTIONS[name] for name in page.actions],
        "columns": [help_registry.COLUMNS[name] for name in page.columns],
    }


@register.simple_tag
def help_url(target: str) -> str:
    """Return the URL of a help target: a guide page's slug, optionally with "#anchor"."""
    from nrmps.help_views import help_url as url

    return url(target)
