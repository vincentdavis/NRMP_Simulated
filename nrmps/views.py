from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods

from .forms import SignupForm


@require_GET
def index(request):
    """Home page (index)."""
    return render(request, "nrmps/index.html")


@require_GET
def account(request):
    """User account page; shows basic info if authenticated."""
    return render(request, "nrmps/account.html")


@require_GET
def contact(request):
    """Contact information page."""
    return render(request, "nrmps/contact.html")


@require_GET
def privacy(request):
    """Privacy policy page."""
    return render(request, "nrmps/privacy.html")


@require_GET
def terms(request):
    """Terms of service page."""
    return render(request, "nrmps/terms.html")


@require_http_methods(["GET", "POST"])
def signup(request):
    """Create a new user account.

    On success, logs the user in and redirects to the index page.
    """
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("nrmps:index")
    else:
        form = SignupForm()
    return render(request, "nrmps/signup.html", {"form": form})
