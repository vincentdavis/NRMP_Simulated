"""Account pages: sign-up, profile, email confirmation, personal data export and account deletion."""

import time

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_not_required
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .accounts import export_user_data, send_verification_email, verify_token
from .forms import DeleteAccountForm, ProfileForm, SignupForm

# Minimum seconds between two confirmation emails requested from the account page.
RESEND_INTERVAL = 60


@login_not_required
@require_http_methods(["GET", "POST"])
def signup(request):
    """Create an account, sign the user in and send the email confirmation link."""
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            send_verification_email(request, user)
            request.session["verification_sent_at"] = time.time()
            messages.success(request, f"Welcome! We sent a confirmation link to {user.email}.")
            return redirect("nrmps:simulation_list")
    else:
        form = SignupForm()
    return render(request, "nrmps/signup.html", {"form": form})


@require_GET
def account(request):
    """Show the account details, email status and account actions."""
    return render(request, "nrmps/account.html")


@require_http_methods(["GET", "POST"])
def account_edit(request):
    """Edit the full name and email address; a new address must be confirmed again."""
    user = request.user
    previous_email = user.email
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save(commit=False)
            email_changed = user.email.lower() != previous_email.lower()
            if email_changed:
                user.email_verified_at = None
            user.save()
            if email_changed:
                send_verification_email(request, user)
                request.session["verification_sent_at"] = time.time()
                messages.success(request, f"Saved. We sent a confirmation link to {user.email}.")
            else:
                messages.success(request, "Your details were saved.")
            return redirect("nrmps:account")
    else:
        form = ProfileForm(instance=user)
    return render(request, "nrmps/account_edit.html", {"form": form})


@login_not_required
@require_GET
def verify_email(request, token: str):
    """Confirm an email address from the link in the confirmation email."""
    user = verify_token(token)
    if user is None:
        messages.error(
            request, "This confirmation link is not valid or has expired. Request a new one on your account page."
        )
    else:
        messages.success(request, f"Thank you, {user.email} is confirmed.")
    return redirect("nrmps:account" if request.user.is_authenticated else "nrmps:login")


@require_POST
def resend_verification(request):
    """Send a new confirmation link, at most once a minute."""
    user = request.user
    if not user.email:
        messages.error(request, "Add an email address first.")
    elif user.email_verified:
        messages.info(request, "Your email address is already confirmed.")
    elif time.time() - request.session.get("verification_sent_at", 0) < RESEND_INTERVAL:
        messages.warning(request, "A confirmation link was sent less than a minute ago. Please check your inbox.")
    else:
        send_verification_email(request, user)
        request.session["verification_sent_at"] = time.time()
        messages.success(request, f"We sent a new confirmation link to {user.email}.")
    return redirect("nrmps:account")


@require_GET
def account_export(request):
    """Download everything stored for the account as a ZIP file."""
    archive = export_user_data(request.user)
    filename = f"nrmp-simulations-{request.user.get_username()}-{timezone.now():%Y-%m-%d}.zip"
    return FileResponse(archive, as_attachment=True, filename=filename, content_type="application/zip")


@require_http_methods(["GET", "POST"])
def account_delete(request):
    """Delete the account and all its simulations after the password is confirmed."""
    if request.method == "POST":
        form = DeleteAccountForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, "Your account and all its simulations were deleted.")
            return redirect("nrmps:index")
    else:
        form = DeleteAccountForm(request.user)
    return render(request, "nrmps/account_delete.html", {"form": form})
