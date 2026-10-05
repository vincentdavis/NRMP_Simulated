"""Template tags for search engines (nrmps.seo): structured data in the page's head."""

import json
from typing import Any

from django import template
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe

register = template.Library()

# As Django's json_script: characters that could end the script element or start markup are written as escapes.
_ESCAPES = {ord(">"): "\\u003E", ord("<"): "\\u003C", ord("&"): "\\u0026"}


@register.simple_tag
def jsonld(data: dict[str, Any] | None) -> SafeString:
    """Render structured data as a JSON-LD script element (nothing without data).

    A data block, not a script that runs, so the Content Security Policy does not apply to it.
    """
    if not data:
        return SafeString("")
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")).translate(_ESCAPES)
    return format_html('<script type="application/ld+json">{}</script>', mark_safe(text))  # noqa: S308 (escaped above)
