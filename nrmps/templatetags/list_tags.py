"""Template tags for sortable, paginated list pages."""

from django import template

register = template.Library()


@register.inclusion_tag("nrmps/components/sort_th.html", takes_context=True)
def sort_th(context, key: str, label: str, align: str = "left"):
    """Render a sortable column header that toggles the order and exposes the current sort with aria-sort."""
    active = context.get("sort") == key
    order = context.get("order", "asc")
    return {
        "key": key,
        "label": label,
        "align": align,
        "active": active,
        "order": order,
        "next_order": "desc" if active and order == "asc" else "asc",
        "aria_sort": ("ascending" if order == "asc" else "descending") if active else "",
        "page_size": context.get("page_size"),
    }
