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

import logging
from .forms import SignupForm, SimulationForm, StudentsUploadForm, SchoolsUploadForm, SimulationConfigForm
from .models import Simulation, Interview

logger = logging.getLogger(__name__)


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
        # Fallback: infer form by field names if form_id missing or unexpected
        if not form_id:
            if any(k in request.POST for k in ("number_of_applicants", "number_of_schools", "applicant_score_mean")):
                form_id = "config"
            else:
                form_id = "simulation"
        logger.info("simulation_manage POST", extra={
            "user_id": getattr(request.user, "id", None),
            "simulation_id": sim.id,
            "form_id": form_id,
        })
        if form_id == "config":
            # Handle SimulationConfig form
            if config_instance is not None:
                logger.debug("Binding SimulationConfigForm with existing instance", extra={"config_id": config_instance.id})
                config_form = SimulationConfigForm(request.POST, instance=config_instance)
            else:
                logger.debug("Binding SimulationConfigForm for create")
                config_form = SimulationConfigForm(request.POST)
            # Keep simulation form for rendering
            form = SimulationForm(instance=sim)
            valid = config_form.is_valid()
            # Log validity and errors in the message so they are visible even without structured formatting
            logger.info(
                "SimulationConfigForm validated valid=%s errors=%s post_keys=%s",
                valid,
                None if valid else config_form.errors.as_json(),
                list(request.POST.keys()),
                extra={
                    "valid": valid,
                    "errors": config_form.errors.get_json_data() if not valid else None,
                    "post_sizes": {k: len(v) if hasattr(v, "__len__") else None for k, v in request.POST.items()},
                },
            )
            if valid:
                cfg = config_form.save(commit=False)
                cfg.simulation = sim
                is_update = bool(getattr(cfg, "id", None))
                cfg.save()
                logger.info(
                    "SimulationConfig saved config_id=%s simulation_id=%s updated=%s",
                    cfg.id,
                    sim.id,
                    is_update,
                    extra={
                        "config_id": cfg.id,
                        "simulation_id": sim.id,
                        "updated": is_update,
                    },
                )
                return redirect("nrmps:simulation_manage", pk=sim.pk)
        else:
            # Default: handle Simulation basic form
            form = SimulationForm(request.POST, instance=sim)
            config_form = SimulationConfigForm(instance=config_instance)
            valid = form.is_valid()
            logger.info(
                "SimulationForm validated valid=%s errors=%s",
                valid,
                None if valid else form.errors.as_json(),
                extra={
                    "valid": valid,
                    "errors": form.errors.get_json_data() if not valid else None,
                },
            )
            if valid:
                form.save()
                logger.info("Simulation saved simulation_id=%s", sim.id, extra={"simulation_id": sim.id})
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
    writer.writerow(["name", "score", "score_meta"])
    for s in sim.students.all().only("name", "score", "score_meta"):
        score_meta_str = json.dumps(s.score_meta or {}, ensure_ascii=False)
        writer.writerow([s.name, s.score, score_meta_str])
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
    writer.writerow(["name", "capacity", "score", "score_meta"])
    for s in sim.schools.all().only("name", "capacity", "score", "score_meta"):
        score_meta_str = json.dumps(s.score_meta or {}, ensure_ascii=False)
        writer.writerow([s.name, s.capacity, s.score, score_meta_str])
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


# --- Interview section ---
@login_required
@require_http_methods(["POST"])
def simulation_initialize_interviews(request, pk: int):
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    from .simulation_engine import initialize_interview

    initialize_interview(sim)
    return render(request, "nrmps/partials/_interview_counts.html", {"simulation": sim})


@login_required
@require_http_methods(["POST"])
def simulation_students_rate_pre_interview(request, pk: int):
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    from .simulation_engine import students_rate_schools_pre_interview

    students_rate_schools_pre_interview(sim)
    return render(request, "nrmps/partials/_interview_counts.html", {"simulation": sim})


@login_required
@require_GET
def simulation_interviews(request, pk: int):
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()

    try:
        page_size = int(request.GET.get("page_size", 100))
    except (TypeError, ValueError):
        page_size = 100
    if page_size <= 0:
        page_size = 100

    qs = Interview.objects.filter(simulation=sim).select_related("student", "school").order_by("id")
    paginator = Paginator(qs, page_size)
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)

    context = {
        "simulation": sim,
        "page_obj": page_obj,
        "page_size": page_size,
        "page_sizes": [25, 50, 100, 200, 500],
    }
    return render(request, "nrmps/interviews_list.html", context)


@login_required
@require_GET
def simulation_download_interviews(request, pk: int):
    sim = get_object_or_404(Simulation, pk=pk)
    if sim.owner_id != request.user.id:
        raise Http404()
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f"attachment; filename=simulation_{sim.id}_interviews.csv"
    writer = csv.writer(resp)
    writer.writerow([
        "student",
        "school",
        "status",
        "student_pre_observed_score_of_school",
        "school_pre_observed_score_of_student",
        "student_post_observed_score_of_school",
        "school_post_observed_score_of_student",
    ])
    for inter in Interview.objects.filter(simulation=sim).select_related("student", "school"):
        writer.writerow([
            inter.student.name,
            inter.school.name,
            inter.status,
            inter.student_pre_observed_score_of_school,
            inter.school_pre_observed_score_of_student,
            inter.student_post_observed_score_of_school,
            inter.school_post_observed_score_of_student,
        ])
    return resp
