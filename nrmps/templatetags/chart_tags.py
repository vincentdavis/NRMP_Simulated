"""The chart figure (plan steps 3.8 and 5.1): a chart with its caption and "?" help from the chart catalog."""

from typing import Any

from django import template

from nrmps import help_registry

register = template.Library()


@register.inclusion_tag("nrmps/components/chart_figure.html")
def chart_figure(
    chart: dict[str, Any] | None,
    key: str,
    kind: str,
    *,
    table: str = "",
    height: str = "h-64",
    x_label: str = "",
    y_label: str = "",
    payload: str = "",
    switch_on: bool = False,
) -> dict[str, Any]:
    """Render one chart: `chart` from nrmps.charts (payload, summary, rows), `key` its entry in the chart catalog.

    `kind` is the builder in static/js/nrmp-charts.js; `table` the data table under it (histogram, demand, flow,
    funnel, choice, sorting, fill, by_strength, or none); `payload` the id of another figure's payload to draw
    instead (the Lorenz curve reuses the demand's);
    `switch_on` starts the chart's switch on (the reader's remembered choice, if any, still wins). The
    caption, the "?" help and the colour come from the catalog; an undescribed key raises KeyError, so a page that
    shows one fails its tests.
    """
    return {
        "chart": chart or {},
        "key": key,
        "kind": kind,
        "entry": help_registry.chart(key),
        "element_id": help_registry.chart_anchor(key),
        "table": table,
        "height": height,
        "x_label": x_label,
        "y_label": y_label,
        "payload": payload,
        "switch_on": switch_on,
    }
