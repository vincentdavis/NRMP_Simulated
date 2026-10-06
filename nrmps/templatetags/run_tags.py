"""Template tags of a run's pages, which show a user's run or a saved example run (nrmps.run_views.RunPages)."""

from typing import Any

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def run_url(context: template.Context, page: str, **kwargs: Any) -> str:
    """Return the address of page `page` of the run being shown.

    {% run_url "match" %}, {% run_url "applicant" index=row.number %}, {% run_url "download" name="match.csv" %}:
    the user's run under /simulations/, or the example under /examples/. The context needs `pages`.
    """
    address: str = context["pages"].url(page, **kwargs)
    return address
