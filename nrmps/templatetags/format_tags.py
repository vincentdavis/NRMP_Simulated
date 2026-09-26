"""Number formatting for the result pages."""

from typing import Any

from django import template

register = template.Library()


@register.filter
def percent(value: Any, digits: int = 1) -> str:
    """Format a share (0 to 1) as a percentage with `digits` decimals, or "-" when there is none."""
    if value is None or value == "":
        return "-"
    try:
        return f"{float(value) * 100:.{int(digits)}f}%"
    except TypeError, ValueError:
        return "-"
