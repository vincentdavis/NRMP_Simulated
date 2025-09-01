from pathlib import Path

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.conf import settings

from .forms import SignupForm, SimulationForm, StudentsUploadForm, SchoolsUploadForm, SimulationConfigForm
from .models import Simulation


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


@login_required
@require_GET
def simulation_list(request):
    """List simulations for the authenticated user."""
    sims = Simulation.objects.filter(owner=request.user).order_by("-id")
    return render(request, "nrmps/simulations_list.html", {"simulations": sims})


@login_required
@require_http_methods(["GET", "POST"])
def simulation_create(request):
    """Create a new Simulation for the current user."""
    if request.method == "POST":
        form = SimulationForm(request.POST)
        if form.is_valid():
            sim = form.save(commit=False)
            sim.owner = request.user
            sim.save()
            return redirect("nrmps:simulation_manage", pk=sim.pk)
    else:
        form = SimulationForm()
    return render(request, "nrmps/simulation_form.html", {"form": form, "create": True})


@login_required
@require_http_methods(["GET", "POST"])
def simulation_manage(request, pk: int):
    """Manage a Simulation: edit basic fields, perform population actions."""
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()

    # Latest config if it exists
    config_instance = sim.configs.order_by("-id").first()

    if request.method == "POST":
        form_id = request.POST.get("form_id")
        if form_id == "config":
            # Handle SimulationConfig form
            if config_instance is not None:
                config_form = SimulationConfigForm(request.POST, instance=config_instance)
            else:
                config_form = SimulationConfigForm(request.POST)
            # Keep simulation form for rendering
            form = SimulationForm(instance=sim)
            if config_form.is_valid():
                cfg = config_form.save(commit=False)
                cfg.simulation = sim
                cfg.save()
                return redirect("nrmps:simulation_manage", pk=sim.pk)
        else:
            # Default: handle Simulation basic form
            form = SimulationForm(request.POST, instance=sim)
            config_form = SimulationConfigForm(instance=config_instance)
            if form.is_valid():
                form.save()
                return redirect("nrmps:simulation_manage", pk=sim.pk)
    else:
        form = SimulationForm(instance=sim)
        config_form = SimulationConfigForm(instance=config_instance)

    context = {
        "simulation": sim,
        "form": form,
        "config_form": config_form,
        "students_upload_form": StudentsUploadForm(),
        "schools_upload_form": SchoolsUploadForm(),
    }
    return render(request, "nrmps/simulation_manage.html", context)


@login_required
@require_http_methods(["POST"])
def simulation_delete(request, pk: int):
    """Delete a Simulation."""
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    sim.delete()
    return redirect("nrmps:simulation_list")


# --- HTMX population actions ---

@login_required
@require_http_methods(["POST"])
def simulation_delete_students(request, pk: int):
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    sim.delete_students()
    return render(request, "nrmps/partials/_population_counts.html", {"simulation": sim})


@login_required
@require_http_methods(["POST"])
def simulation_delete_schools(request, pk: int):
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    sim.delete_schools()
    return render(request, "nrmps/partials/_population_counts.html", {"simulation": sim})


@login_required
@require_http_methods(["POST"])
def simulation_create_students(request, pk: int):
    """(Re)create student population based on the latest SimulationConfig."""
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    sim.create_students()
    return render(request, "nrmps/partials/_population_counts.html", {"simulation": sim})


@login_required
@require_http_methods(["POST"])
def simulation_create_schools(request, pk: int):
    """(Re)create school population based on the latest SimulationConfig."""
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    sim.create_schools()
    return render(request, "nrmps/partials/_population_counts.html", {"simulation": sim})


@login_required
@require_http_methods(["POST"])
def simulation_upload_students(request, pk: int):
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    form = StudentsUploadForm(request.POST, request.FILES)
    if form.is_valid():
        file = form.cleaned_data["file"]
        data_dir = Path(getattr(settings, "BASE_DIR", ".")) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        dest = data_dir / f"simulation_{sim.id}_students.csv"
        with dest.open("wb") as out:
            for chunk in file.chunks():
                out.write(chunk)
        sim.upload_students()
    return render(request, "nrmps/partials/_population_counts.html", {"simulation": sim})


@login_required
@require_http_methods(["POST"])
def simulation_upload_schools(request, pk: int):
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    form = SchoolsUploadForm(request.POST, request.FILES)
    if form.is_valid():
        file = form.cleaned_data["file"]
        data_dir = Path(getattr(settings, "BASE_DIR", ".")) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        dest = data_dir / f"simulation_{sim.id}_schools.csv"
        with dest.open("wb") as out:
            for chunk in file.chunks():
                out.write(chunk)
        sim.upload_schools()
    return render(request, "nrmps/partials/_population_counts.html", {"simulation": sim})


# --- CSV downloads ---

@login_required
@require_GET
def simulation_download_students(request, pk: int):
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    rows = sim.students.all().values_list("name", "score")
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f"attachment; filename=simulation_{sim.id}_students.csv"
    resp.write("name,score\n")
    for name, score in rows:
        resp.write(f"{name},{score}\n")
    return resp


@login_required
@require_GET
def simulation_download_schools(request, pk: int):
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    rows = sim.schools.all().values_list("name", "capacity", "score")
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f"attachment; filename=simulation_{sim.id}_schools.csv"
    resp.write("name,capacity,score\n")
    for name, capacity, score in rows:
        resp.write(f"{name},{capacity},{score}\n")
    return resp
