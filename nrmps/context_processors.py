"""Template context shared by every page."""

from django.conf import settings

from .limits import max_pairs
from .seo import page_context


def site(request):
    """Expose the public contact details, project links and DEBUG (for hints to developers) to templates.

    Also `seo`, what the page's <head> tells search engines (nrmps.seo), and the search consoles' verification codes.
    """
    return {
        "DEBUG": settings.DEBUG,
        "CONTACT_EMAIL": settings.CONTACT_EMAIL,
        "PROJECT_URL": settings.PROJECT_URL,
        "ISSUES_URL": f"{settings.PROJECT_URL}/issues",
        "MAX_PAIRS": max_pairs(),
        "seo": page_context(request),
        "GOOGLE_SITE_VERIFICATION": settings.GOOGLE_SITE_VERIFICATION,
        "BING_SITE_VERIFICATION": settings.BING_SITE_VERIFICATION,
    }
