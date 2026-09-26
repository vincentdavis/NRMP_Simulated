"""Email and account lifecycle (plan step 1.9: CRIT-7, CRIT-4, UX-15)."""

import io
import json
import re
import zipfile

import pytest
from django.core import mail, signing
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse

from nrmps.accounts import VERIFY_SALT, verification_token
from nrmps.engine import MODEL_VERSION
from nrmps.models import Simulation, User

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def _link(message) -> str:
    """Return the path of the first link in an email."""
    match = re.search(r"https?://[^\s]+", message.body)
    assert match, message.body
    return re.sub(r"^https?://[^/]+", "", match.group(0))


def _signup(client, username="bob", email="bob@example.com"):
    data = {"username": username, "email": email, "password1": PASSWORD, "password2": PASSWORD}
    return client.post(reverse("nrmps:signup"), data)


# --- Sign-up and email addresses -----------------------------------------------------------------------------------


def test_email_is_required_at_signup(client):
    response = client.post(reverse("nrmps:signup"), {"username": "bob", "password1": PASSWORD, "password2": PASSWORD})
    assert response.status_code == 200
    assert not User.objects.filter(username="bob").exists()


def test_email_must_be_unique_ignoring_case(client, user):
    response = _signup(client, email="ALICE@example.com")
    assert response.status_code == 200
    assert "Another account already uses this email address." in response.content.decode()


def test_database_rejects_duplicate_emails_but_allows_several_empty_ones(user):
    User.objects.create_user("carol", email="", password=PASSWORD)
    User.objects.create_user("dave", email="", password=PASSWORD)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("eve", email="Alice@Example.com", password=PASSWORD)


def test_signup_sends_a_confirmation_link_that_confirms_the_address(client):
    _signup(client)
    user = User.objects.get(username="bob")
    assert not user.email_verified
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["bob@example.com"]
    response = client.get(_link(mail.outbox[0]))
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.email_verified


def test_confirmation_link_works_when_signed_out(client, user):
    token = verification_token(user)
    response = client.get(reverse("nrmps:verify_email", kwargs={"token": token}))
    assert response["Location"] == reverse("nrmps:login")
    user.refresh_from_db()
    assert user.email_verified


def test_confirmation_link_for_an_old_address_does_not_confirm_a_new_one(client, user):
    token = verification_token(user)
    user.email = "new@example.com"
    user.save()
    client.get(reverse("nrmps:verify_email", kwargs={"token": token}))
    user.refresh_from_db()
    assert not user.email_verified


def test_tampered_or_expired_links_are_rejected(client, user, settings):
    bad = verification_token(user)[:-2] + "xx"
    client.get(reverse("nrmps:verify_email", kwargs={"token": bad}))
    settings.PASSWORD_RESET_TIMEOUT = -1  # every token is now too old
    client.get(
        reverse(
            "nrmps:verify_email",
            kwargs={"token": signing.dumps({"user": user.pk, "email": user.email}, salt=VERIFY_SALT)},
        )
    )
    user.refresh_from_db()
    assert not user.email_verified


def test_resending_the_link_is_limited_to_once_a_minute(auth_client):
    auth_client.post(reverse("nrmps:resend_verification"))
    auth_client.post(reverse("nrmps:resend_verification"))
    assert len(mail.outbox) == 1


def test_changing_the_email_requires_confirming_it_again(auth_client, user):
    user.email_verified_at = user.date_joined
    user.save()
    response = auth_client.post(reverse("nrmps:account_edit"), {"full_name": "Alice A", "email": "alice@new.example"})
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.email == "alice@new.example"
    assert user.full_name == "Alice A"
    assert not user.email_verified
    assert mail.outbox[0].to == ["alice@new.example"]


def test_account_edit_rejects_another_accounts_email(auth_client, other_user):
    response = auth_client.post(reverse("nrmps:account_edit"), {"full_name": "", "email": "MALLORY@example.com"})
    assert response.status_code == 200
    assert "Another account already uses this email address." in response.content.decode()


# --- Password reset ------------------------------------------------------------------------------------------------


def test_password_reset_by_email(client, user):
    response = client.post(reverse("nrmps:password_reset"), {"email": "alice@example.com"})
    assert response["Location"] == reverse("nrmps:password_reset_done")
    assert len(mail.outbox) == 1
    response = client.get(_link(mail.outbox[0]), follow=True)
    set_password_url = response.redirect_chain[-1][0]
    new = "Brand-New-Password-42"
    response = client.post(set_password_url, {"new_password1": new, "new_password2": new})
    assert response["Location"] == reverse("nrmps:password_reset_complete")
    user.refresh_from_db()
    assert user.check_password(new)


def test_password_reset_does_not_reveal_whether_an_account_exists(client):
    response = client.post(reverse("nrmps:password_reset"), {"email": "nobody@example.com"})
    assert response["Location"] == reverse("nrmps:password_reset_done")
    assert mail.outbox == []


def test_login_page_links_to_password_reset(client):
    assert reverse("nrmps:password_reset") in client.get(reverse("nrmps:login")).content.decode()


# --- Export and deletion ---------------------------------------------------------------------------------------------


def test_data_export_contains_account_simulations_and_runs(auth_client, finished_run, simulation):
    response = auth_client.get(reverse("nrmps:account_export"))
    assert response["Content-Type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content)))
    names = archive.namelist()
    assert "account.json" in names
    assert json.loads(archive.read("account.json"))["username"] == "alice"
    folder = f"simulations/{simulation.pk}-test-simulation"
    for name in ("simulation.json", "runs/1/run.json", "runs/1/applicants.csv", "runs/1/programs.csv"):
        assert f"{folder}/{name}" in names
    assert json.loads(archive.read(f"{folder}/simulation.json"))["params"] == simulation.params
    record = json.loads(archive.read(f"{folder}/runs/1/run.json"))
    assert record["seed"] == 12345
    assert record["stamps"]["model_version"] == MODEL_VERSION
    assert archive.read(f"{folder}/runs/1/applicants.csv").decode().count("\n") == 61


def test_account_deletion_needs_the_password(auth_client, user, simulation):
    response = auth_client.post(reverse("nrmps:account_delete"), {"password": "wrong"})
    assert response.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()


def test_account_deletion_removes_the_account_and_its_simulations(auth_client, user, simulation):
    response = auth_client.post(reverse("nrmps:account_delete"), {"password": PASSWORD}, follow=True)
    assert "Your account and all its simulations were deleted." in response.content.decode()
    assert not User.objects.filter(pk=user.pk).exists()
    assert not Simulation.objects.filter(pk=simulation.pk).exists()
    assert auth_client.get(reverse("nrmps:account")).status_code == 302  # signed out


# --- Migration -----------------------------------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_migration_keeps_duplicate_emails_on_the_oldest_account_only():
    before = [("nrmps", "0010_user_full_name_not_null")]
    executor = MigrationExecutor(connection)
    executor.migrate(before)
    old_user = executor.loader.project_state(before).apps.get_model("nrmps", "User")
    old_user.objects.create(username="first", email="Same@Example.com", password="x")
    old_user.objects.create(username="second", email="same@example.com", password="x")
    old_user.objects.create(username="other", email="other@example.com", password="x")

    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())

    emails = dict(User.objects.values_list("username", "email"))
    assert emails == {"first": "Same@Example.com", "second": "", "other": "other@example.com"}
