"""Template context shared by every page."""

from django.conf import settings

from .limits import max_pairs


def site(request):
    """Expose the public contact details and project links to templates."""
    return {
        "CONTACT_EMAIL": settings.CONTACT_EMAIL,
        "PROJECT_URL": settings.PROJECT_URL,
        "ISSUES_URL": f"{settings.PROJECT_URL}/issues",
        "MAX_PAIRS": max_pairs(),
    }
