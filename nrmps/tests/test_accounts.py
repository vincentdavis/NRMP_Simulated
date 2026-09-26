"""Account basics (plan step 0.8: UX-15, ENG-20, CRIT-6)."""

import pytest
from django.test import RequestFactory
from django.urls import reverse

from nrmps.security import client_ip

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def _login(client, username, password, **headers):
    return client.post(reverse("nrmps:login"), {"username": username, "password": password}, headers=headers)


def test_wrong_password_says_what_is_wrong(client, user):
    """The login page shows Django's actual message, not only "Please correct the errors below" (UX-15)."""
    body = _login(client, "alice", "wrong").content.decode()
    assert "Please enter a correct username and password" in body


def test_account_page_links_to_the_password_change_page(auth_client):
    body = auth_client.get(reverse("nrmps:account")).content.decode()
    assert reverse("nrmps:password_change") in body
    assert "/admin/password_change/" not in body


def test_password_change_requires_login(client):
    response = client.get(reverse("nrmps:password_change"))
    assert response.status_code == 302
    assert reverse("nrmps:login") in response["Location"]


def test_password_can_be_changed_without_the_admin(client, user):
    """A regular (non-staff) user can change their password (ENG-20)."""
    client.force_login(user)
    assert client.get(reverse("nrmps:password_change")).status_code == 200
    new = "Another-Horse-Battery-7"
    response = client.post(
        reverse("nrmps:password_change"),
        {"old_password": PASSWORD, "new_password1": new, "new_password2": new},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("nrmps:password_change_done")
    user.refresh_from_db()
    assert user.check_password(new)


def test_password_change_shows_validation_errors(auth_client):
    response = auth_client.post(
        reverse("nrmps:password_change"),
        {"old_password": "wrong", "new_password1": "short", "new_password2": "short"},
    )
    body = response.content.decode()
    assert response.status_code == 200
    assert "Your old password was entered incorrectly" in body


def test_repeated_failures_lock_out_that_username_from_that_client(client, user, other_user):
    """The 5th failure locks the username from that client, even with the right password (CRIT-6)."""
    for _ in range(4):
        assert _login(client, "alice", "wrong").status_code == 200
    assert _login(client, "alice", "wrong").status_code == 429
    response = _login(client, "alice", PASSWORD)
    assert response.status_code == 429
    assert b"Too many failed sign-in attempts" in response.content
    # Another account from the same client is not affected.
    assert _login(client, "mallory", PASSWORD).status_code == 302


def test_lockout_is_per_client_behind_the_proxy(client, user):
    """One client's failures do not lock the account for everyone.

    Behind Railway's proxy the real client address comes from X-Forwarded-For.
    """
    for _ in range(5):
        _login(client, "alice", "wrong", x_forwarded_for="203.0.113.7")
    assert _login(client, "alice", PASSWORD, x_forwarded_for="203.0.113.7").status_code == 429
    assert _login(client, "alice", PASSWORD, x_forwarded_for="198.51.100.9").status_code == 302


def test_successful_sign_in_clears_earlier_failures(client, user):
    for _ in range(4):
        _login(client, "alice", "wrong")
    assert _login(client, "alice", PASSWORD).status_code == 302
    client.post(reverse("nrmps:logout"))
    for _ in range(4):
        _login(client, "alice", "wrong")
    assert _login(client, "alice", PASSWORD).status_code == 302


@pytest.mark.parametrize(
    ("forwarded", "count", "expected"),
    [
        (None, 1, "10.0.0.1"),  # no proxy header: the socket address
        ("203.0.113.7", 1, "203.0.113.7"),  # appended by our proxy
        ("6.6.6.6, 203.0.113.7", 1, "203.0.113.7"),  # a forged first entry is ignored
        ("6.6.6.6, 203.0.113.7, 10.1.1.1", 2, "203.0.113.7"),  # two proxies
        ("203.0.113.7", 0, "10.0.0.1"),  # no trusted proxy: the header is ignored
        ("203.0.113.7", 2, "10.0.0.1"),  # fewer hops than proxies: fall back to the socket address
    ],
)
def test_client_ip_trusts_only_the_proxy_appended_address(settings, forwarded, count, expected):
    settings.TRUSTED_PROXY_COUNT = count
    headers = {"REMOTE_ADDR": "10.0.0.1"}
    if forwarded:
        headers["HTTP_X_FORWARDED_FOR"] = forwarded
    assert client_ip(RequestFactory().get("/", **headers)) == expected
