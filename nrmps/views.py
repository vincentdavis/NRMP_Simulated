from pathlib import Path
import csv
import json

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.paginator import Paginator

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
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f"attachment; filename=simulation_{sim.id}_students.csv"
    writer = csv.writer(resp)
    writer.writerow(["name", "score", "meta_stddev", "score_meta"])
    for s in sim.students.all().only("name", "score", "meta_stddev", "score_meta"):
        score_meta_str = json.dumps(s.score_meta or {}, ensure_ascii=False)
        writer.writerow([s.name, s.score, s.meta_stddev or 0.0, score_meta_str])
    return resp


@login_required
@require_GET
def simulation_download_schools(request, pk: int):
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f"attachment; filename=simulation_{sim.id}_schools.csv"
    writer = csv.writer(resp)
    writer.writerow(["name", "capacity", "score", "meta_stddev", "score_meta"])
    for s in sim.schools.all().only("name", "capacity", "score", "meta_stddev", "score_meta"):
        score_meta_str = json.dumps(s.score_meta or {}, ensure_ascii=False)
        writer.writerow([s.name, s.capacity, s.score, s.meta_stddev or 0.0, score_meta_str])
    return resp



@login_required
@require_GET
def simulation_students(request, pk: int):
    """List students for a simulation with sorting and pagination (default 100)."""
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()

    # Sorting
    sort = request.GET.get("sort", "name").lower()
    order = request.GET.get("order", "asc").lower()
    allowed = {
        "id": "id",
        "name": "name",
        "score": "score",
        "meta_stddev": "meta_stddev",
    }
    sort_field = allowed.get(sort, "name")
    ordering = sort_field if order != "desc" else f"-{sort_field}"

    # Page size
    try:
        page_size = int(request.GET.get("page_size", 100))
    except (TypeError, ValueError):
        page_size = 100
    if page_size <= 0:
        page_size = 100

    qs = sim.students.all().order_by(ordering)
    paginator = Paginator(qs, page_size)
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)

    context = {
        "simulation": sim,
        "page_obj": page_obj,
        "sort": sort,
        "order": order,
        "page_size": page_size,
        "page_sizes": [25, 50, 100, 200, 500],
    }
    return render(request, "nrmps/students_list.html", context)


@login_required
@require_GET
def simulation_schools(request, pk: int):
    """List schools for a simulation with sorting and pagination (default 100)."""
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()

    sort = request.GET.get("sort", "name").lower()
    order = request.GET.get("order", "asc").lower()
    allowed = {
        "id": "id",
        "name": "name",
        "capacity": "capacity",
        "score": "score",
        "meta_stddev": "meta_stddev",
    }
    sort_field = allowed.get(sort, "name")
    ordering = sort_field if order != "desc" else f"-{sort_field}"

    try:
        page_size = int(request.GET.get("page_size", 100))
    except (TypeError, ValueError):
        page_size = 100
    if page_size <= 0:
        page_size = 100

    qs = sim.schools.all().order_by(ordering)
    paginator = Paginator(qs, page_size)
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)

    context = {
        "simulation": sim,
        "page_obj": page_obj,
        "sort": sort,
        "order": order,
        "page_size": page_size,
        "page_sizes": [25, 50, 100, 200, 500],
    }
    return render(request, "nrmps/schools_list.html", context)
