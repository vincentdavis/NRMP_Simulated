"""Template tags for the site navigation."""

from django import template
from django.urls import reverse
from django.utils.html import format_html

register = template.Library()


@register.simple_tag(takes_context=True)
def nav_link(context, url_name: str, label: str, section: str = ""):
    """Render a menu link, marked as current when the page belongs to its section.

    `section` is a prefix of URL names (for example "simulation" matches simulation_list, simulation_manage ...);
    without it, only `url_name` itself is current.
    """
    match = getattr(context.get("request"), "resolver_match", None)
    current_name = match.url_name if match else ""
    current = bool(current_name) and (current_name.startswith(section) if section else current_name == url_name)
    if current:
        return format_html(
            '<li><a class="menu-active" aria-current="page" href="{}">{}</a></li>', reverse(url_name), label
        )
    return format_html('<li><a href="{}">{}</a></li>', reverse(url_name), label)
