"""Browser tests (Playwright) against pytest-django's live server.

Run with `uv run pytest -m e2e`. They need the built CSS (`npm run build` in theme/static_src) and Playwright's
Chromium (`uv run playwright install chromium`).
"""

import os

import pytest

# Playwright's sync API runs an event loop in the test thread; the ORM calls in fixtures are still synchronous.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

from nrmps.tests.conftest import PASSWORD


@pytest.fixture
def live(live_server, settings):
    """Return the live server URL, with cookies allowed over plain HTTP."""
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False
    return live_server.url


@pytest.fixture
def logged_in_page(page, live, user):
    """Return a Playwright page signed in as `user` through the login form."""
    page.goto(f"{live}/login/")
    page.fill("#id_username", user.username)
    page.fill("#id_password", PASSWORD)
    page.get_by_role("button", name="Log in", exact=True).click()
    page.wait_for_url(f"{live}/")
    return page
