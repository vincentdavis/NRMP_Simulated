import csv
import inspect
import json
import logging

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, connection, transaction
from django.http import Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from . import models
from .exceptions import SimulationError
from .forms import SchoolsUploadForm, SignupForm, SimulationConfigForm, SimulationForm, StudentsUploadForm
from .models import Interview, Simulation, SimulationConfig
from .population_csv import COLUMNS as POPULATION_COLUMNS
from .population_csv import csv_lines, parse_population_csv

logger = logging.getLogger(__name__)


PAGE_SIZES = [25, 50, 100, 200, 500]


def _render_stage_cards(
    request,
    simulation,
    *,
    error: str | None = None,
    error_stage: str | None = None,
    error_details: list[str] | None = None,
):
    """Render every stage card, plus an out-of-band swap of the workflow stepper.

    Every HTMX step action returns this, so no card goes stale when a step changes another stage's data (for example
    recreating applicants deletes all interview rows). `error` is shown in the card of `error_stage`.
    """
    simulation.refresh_from_db()
    context = {
        "simulation": simulation,
        "stages": simulation.get_workflow_stages(),
        "error": error,
        "error_stage": error_stage,
        "error_details": error_details or [],
    }
    cards = render(request, "nrmps/partials/_stage_cards.html", context).content.decode()
    stepper = render(request, "nrmps/partials/_workflow_steps.html", context | {"oob": True}).content.decode()
    return HttpResponse(cards + stepper)


def _run_step(request, pk: int, stage: str, action):
    """Run a simulation step for the owner and re-render the stage cards.

    `action(sim)` does the work. A SimulationError (a problem the user can fix) is shown in the card of `stage`;
    any other exception is a bug and propagates.
    """
    sim = get_object_or_404(Simulation, pk=pk, owner=request.user)
    try:
        action(sim)
    except SimulationError as exc:
        logger.info("Simulation step failed simulation_id=%s stage=%s: %s", sim.pk, stage, exc)
        details = getattr(exc, "details", None)
        return _render_stage_cards(request, sim, error=str(exc), error_stage=stage, error_details=details)
    return _render_stage_cards(request, sim)


def _page_size(request) -> int:
    """Return the requested page size if it is one of the offered sizes, else 100."""
    try:
        size = int(request.GET.get("page_size", 100))
    except TypeError, ValueError:
        return 100
    return size if size in PAGE_SIZES else 100


class _Echo:
    """A write-only file-like object that returns what it is given (for streaming CSV)."""

    def write(self, value):
        """Return the value instead of storing it."""
        return value


def _stream_csv(filename: str, header: list[str], rows) -> StreamingHttpResponse:
    """Return a CSV download that is generated row by row instead of built in memory."""
    writer = csv.writer(_Echo())

    def lines():
        yield writer.writerow(header)
        for row in rows:
            yield writer.writerow(row)

    response = StreamingHttpResponse(lines(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_GET
def healthz(request):
    """Health check for the platform: 200 when the database answers, 503 otherwise."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        logger.exception("Health check failed: the database is unavailable")
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


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
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
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
            # Every simulation starts with a valid default configuration, so the population steps work at once.
            with transaction.atomic():
                sim = form.save(commit=False)
                sim.owner = request.user
                sim.save()
                SimulationConfig.objects.create(simulation=sim)
            return redirect("nrmps:simulation_manage", pk=sim.pk)
    else:
        form = SimulationForm()
    return render(request, "nrmps/simulation_form.html", {"form": form, "create": True})


@login_required
@require_http_methods(["GET", "POST"])
def simulation_manage(request, pk: int):
    """Manage a Simulation: edit its basic fields and configuration, and run the steps."""
    sim = get_object_or_404(Simulation, pk=pk, owner=request.user)
    config_instance = sim.configs.order_by("-id").first()
    form = SimulationForm(instance=sim)
    config_form = SimulationConfigForm(instance=config_instance)

    if request.method == "POST":
        # The page has two forms; each posts a hidden form_id.
        if request.POST.get("form_id") == "config":
            config_form = SimulationConfigForm(request.POST, instance=config_instance)
            if config_form.is_valid():
                config = config_form.save(commit=False)
                config.simulation = sim
                config.save()
                return redirect("nrmps:simulation_manage", pk=sim.pk)
            logger.warning("Configuration form invalid simulation_id=%s fields=%s", sim.pk, sorted(config_form.errors))
        else:
            form = SimulationForm(request.POST, instance=sim)
            if form.is_valid():
                form.save()
                return redirect("nrmps:simulation_manage", pk=sim.pk)
            logger.warning("Simulation form invalid simulation_id=%s fields=%s", sim.pk, sorted(form.errors))

    meta_lists = {side: _attribute_list(config_form, f"{side}_meta_preference") for side in ("applicant", "school")}
    context = {
        "simulation": sim,
        "form": form,
        "config_form": config_form,
        "students_upload_form": StudentsUploadForm(),
        "schools_upload_form": SchoolsUploadForm(),
        "stages": sim.get_workflow_stages(),
        # The attribute-list editors read their items from json_script elements; the hidden inputs' fallback values
        # (used without JavaScript) are autoescaped JSON. Nothing user-supplied is marked safe.
        "meta_lists": meta_lists,
        "meta_json": {side: json.dumps(items) for side, items in meta_lists.items()},
    }
    return render(request, "nrmps/simulation_manage.html", context)


def _attribute_list(form, name: str) -> list[str]:
    """Return the attribute list a form field currently holds (submitted or initial) as a list of strings."""
    value = form[name].value()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    return [str(item) for item in value] if isinstance(value, list) else []


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
# Each returns all stage cards (see _render_stage_cards). Replacing or deleting a population deletes every interview
# row by cascade; the model methods reset the pipeline stage accordingly.


@login_required
@require_http_methods(["POST"])
def simulation_delete_students(request, pk: int):
    """Delete all applicants (and, by cascade, all interview rows)."""
    return _run_step(request, pk, "populations", lambda sim: sim.delete_students())


@login_required
@require_http_methods(["POST"])
def simulation_delete_schools(request, pk: int):
    """Delete all programs (and, by cascade, all interview rows)."""
    return _run_step(request, pk, "populations", lambda sim: sim.delete_schools())


@login_required
@require_http_methods(["POST"])
def simulation_create_students(request, pk: int):
    """(Re)create the applicant population from the latest configuration."""
    return _run_step(request, pk, "populations", lambda sim: sim.create_students())


@login_required
@require_http_methods(["POST"])
def simulation_create_schools(request, pk: int):
    """(Re)create the program population from the latest configuration."""
    return _run_step(request, pk, "populations", lambda sim: sim.create_schools())


def _upload(request, pk: int, form_class, kind: str):
    """Replace a population with an uploaded CSV, validated in memory before anything is deleted."""

    def action(sim):
        form = form_class(request.POST, request.FILES)
        if not form.is_valid():
            raise SimulationError("Choose a CSV file to upload.")
        rows = parse_population_csv(form.cleaned_data["file"], kind)
        if kind == "students":
            sim.upload_students(rows)
        else:
            sim.upload_schools(rows)

    return _run_step(request, pk, "populations", action)


@login_required
@require_http_methods(["POST"])
def simulation_upload_students(request, pk: int):
    """Replace the applicants with an uploaded CSV."""
    return _upload(request, pk, StudentsUploadForm, "students")


@login_required
@require_http_methods(["POST"])
def simulation_upload_schools(request, pk: int):
    """Replace the programs with an uploaded CSV."""
    return _upload(request, pk, SchoolsUploadForm, "schools")


# --- CSV downloads ---


def _download_population(request, pk: int, kind: str):
    """Stream a population in the CSV format that the upload accepts."""
    sim = get_object_or_404(Simulation, pk=pk, owner=request.user)
    queryset = sim.students if kind == "students" else sim.schools
    records = queryset.order_by("id").values_list(*POPULATION_COLUMNS[kind]).iterator(chunk_size=2000)
    response = StreamingHttpResponse(csv_lines(kind, records), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="simulation_{sim.id}_{kind}.csv"'
    return response


@login_required
@require_GET
def simulation_download_students(request, pk: int):
    """Download the applicants as CSV (the format the upload accepts)."""
    return _download_population(request, pk, "students")


@login_required
@require_GET
def simulation_download_schools(request, pk: int):
    """Download the programs as CSV (the format the upload accepts)."""
    return _download_population(request, pk, "schools")


@login_required
@require_GET
def simulation_students(request, pk: int):
    """List students for a simulation with sorting and pagination (default 100)."""
    sim = get_object_or_404(Simulation, pk=pk, owner=request.user)

    # Sorting
    sort = request.GET.get("sort", "name").lower()
    order = request.GET.get("order", "asc").lower()
    allowed = {
        "id": "id",
        "name": "name",
        "score": "score",
    }
    sort_field = allowed.get(sort, "name")
    ordering = [sort_field if order != "desc" else f"-{sort_field}", "id"]

    page_size = _page_size(request)
    qs = sim.students.all().order_by(*ordering)
    paginator = Paginator(qs, page_size)
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)

    context = {
        "simulation": sim,
        "page_obj": page_obj,
        "sort": sort,
        "order": order,
        "page_size": page_size,
        "page_sizes": PAGE_SIZES,
    }
    return render(request, "nrmps/students_list.html", context)


@login_required
@require_GET
def simulation_schools(request, pk: int):
    """List schools for a simulation with sorting and pagination (default 100)."""
    sim = get_object_or_404(Simulation, pk=pk, owner=request.user)

    sort = request.GET.get("sort", "name").lower()
    order = request.GET.get("order", "asc").lower()
    allowed = {
        "id": "id",
        "name": "name",
        "capacity": "capacity",
        "score": "score",
    }
    sort_field = allowed.get(sort, "name")
    ordering = [sort_field if order != "desc" else f"-{sort_field}", "id"]

    page_size = _page_size(request)
    qs = sim.schools.all().order_by(*ordering)
    paginator = Paginator(qs, page_size)
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)

    context = {
        "simulation": sim,
        "page_obj": page_obj,
        "sort": sort,
        "order": order,
        "page_size": page_size,
        "page_sizes": PAGE_SIZES,
    }
    return render(request, "nrmps/schools_list.html", context)


# --- Interview section ---


@login_required
@require_http_methods(["POST"])
def simulation_initialize_interviews(request, pk: int):
    """(Re)create the interview rows: one per applicant x program pair."""
    from .simulation_engine import initialize_interview

    return _run_step(request, pk, "initialized", initialize_interview)


@login_required
@require_http_methods(["POST"])
def simulation_compute_pre_interview_all(request, pk: int):
    """Compute true utilities, noisy pre-interview ratings and strict ranks for every interview row."""
    from .simulation_engine import compute_pre_interview_scores_and_rankings

    return _run_step(request, pk, "pre_interview", compute_pre_interview_scores_and_rankings)


@login_required
@require_http_methods(["POST"])
def simulation_compute_post_interview_all(request, pk: int):
    """Compute post-interview ratings and ranks for the pairs that interviewed (none until Phase 3)."""
    from .simulation_engine import compute_post_interview_scores_and_rankings

    return _run_step(request, pk, "post_interview", compute_post_interview_scores_and_rankings)


@login_required
@require_GET
def simulation_interviews(request, pk: int):
    """List interviews for a simulation with sorting and pagination (default 100)."""
    sim = get_object_or_404(Simulation, pk=pk, owner=request.user)

    # Sorting
    sort = request.GET.get("sort", "id").lower()
    order = request.GET.get("order", "asc").lower()
    allowed = {
        "id": "id",
        "student": "student__name",
        "school": "school__name",
        "status": "status",
        "student_pre_score": "student_pre_observed_score_of_school",
        "school_pre_score": "school_pre_observed_score_of_student",
        "student_pre_rank": "students_pre_rank_of_school",
        "school_pre_rank": "schools_pre_rank_of_student",
    }
    sort_field = allowed.get(sort, "id")
    ordering = [sort_field if order != "desc" else f"-{sort_field}", "id"]

    page_size = _page_size(request)
    qs = Interview.objects.filter(simulation=sim).select_related("student", "school").order_by(*ordering)
    paginator = Paginator(qs, page_size)
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)

    context = {
        "simulation": sim,
        "page_obj": page_obj,
        "sort": sort,
        "order": order,
        "page_size": page_size,
        "page_sizes": PAGE_SIZES,
    }
    return render(request, "nrmps/interviews_list.html", context)


INTERVIEW_CSV_COLUMNS = [
    "status",
    "student_true_score_of_school",
    "school_true_score_of_student",
    "student_pre_observed_score_of_school",
    "school_pre_observed_score_of_student",
    "students_pre_rank_of_school",
    "schools_pre_rank_of_student",
    "student_post_observed_score_of_school",
    "school_post_observed_score_of_student",
    "students_post_rank_of_school",
    "schools_post_rank_of_student",
]


@login_required
@require_GET
def simulation_download_interviews(request, pk: int):
    """Download the interview rows (scores and ranks for every applicant-program pair) as CSV."""
    sim = get_object_or_404(Simulation, pk=pk, owner=request.user)
    rows = (
        Interview.objects.filter(simulation=sim)
        .order_by("id")
        .values_list("student__name", "school__name", *INTERVIEW_CSV_COLUMNS)
        .iterator(chunk_size=2000)
    )
    return _stream_csv(f"simulation_{sim.id}_interviews.csv", ["student", "school", *INTERVIEW_CSV_COLUMNS], rows)


@require_GET
def documentation(request):
    """Auto-generated documentation from model and function docstrings."""
    # Configuration for what to include/exclude
    DOC_CONFIG = {
        # Models to exclude completely
        "excluded_models": [
            "AbstractUser",  # Hide Django's AbstractUser
            # 'SimulationConfig',  # Example: uncomment to hide
        ],
        # Models to include (if empty, includes all except excluded)
        "included_models": [
            # 'Simulation', 'Student', 'School',  # Example: only show these
        ],
        # Methods to exclude from all models
        "excluded_methods": [
            "save",
            "delete",
            "clean",
            "full_clean",
            "validate_unique",
            "get_absolute_url",
            "get_deferred_fields",
            "refresh_from_db",
            "adelete",
            "arefresh_from_db",
            "asave",
            "clean_fields",
            "date_error_message",
            "get_constraints",
            "prepare_database_save",
            "save_base",
            "serializable_value",
            "unique_error_message",
            "validate_constraints",
        ],
        # Functions to exclude
        "excluded_functions": [],
        # Check for special attributes to control documentation
        "respect_doc_attributes": True,  # Use __doc_include__ and __doc_exclude__
    }

    def is_documented(obj, name):
        """Check if an object should be documented based on special attributes."""
        if not DOC_CONFIG["respect_doc_attributes"]:
            return True

        # Check for explicit inclusion/exclusion attributes
        if hasattr(obj, "__doc_exclude__") and obj.__doc_exclude__:
            return False
        if hasattr(obj, "__doc_include__") and obj.__doc_include__:
            return True
        return not (hasattr(obj, "__doc_private__") and obj.__doc_private__)

    def extract_docstring_info(obj):
        """Extract and clean docstring from an object."""
        doc = inspect.getdoc(obj)
        if not doc:
            return None
        return doc.strip()

    def get_method_info(cls):
        """Get all methods and their docstrings from a class."""
        methods = []
        for name, method in inspect.getmembers(cls, inspect.isfunction):
            # Skip private methods
            if name.startswith("_"):
                continue

            # Skip excluded methods
            if name in DOC_CONFIG["excluded_methods"]:
                continue

            # Check for documentation attributes
            if not is_documented(method, name):
                continue

            methods.append(
                {
                    "name": name,
                    "docstring": extract_docstring_info(method),
                    "signature": str(inspect.signature(method)) if hasattr(inspect, "signature") else "",
                }
            )
        return methods

    # Extract model information
    model_classes = []
    for name, obj in inspect.getmembers(models, inspect.isclass):
        if not (hasattr(obj, "_meta") and hasattr(obj._meta, "app_label")):
            continue  # Not a Django model

        # Check inclusion/exclusion lists
        if DOC_CONFIG["excluded_models"] and name in DOC_CONFIG["excluded_models"]:
            continue
        if DOC_CONFIG["included_models"] and name not in DOC_CONFIG["included_models"]:
            continue

        # Check for documentation attributes
        if not is_documented(obj, name):
            continue

        model_info = {
            "name": name,
            "docstring": extract_docstring_info(obj),
            "methods": get_method_info(obj),
            "fields": [],
        }

        # Get model fields
        try:
            for field in obj._meta.get_fields():
                # Skip reverse relations and some internal fields
                if hasattr(field, "related_model") and field.many_to_one:
                    continue
                if field.name.endswith("_ptr"):  # Skip OneToOne parent links
                    continue

                field_info = {
                    "name": field.name,
                    "type": field.__class__.__name__,
                    "help_text": getattr(field, "help_text", ""),
                }
                model_info["fields"].append(field_info)
        except AttributeError, TypeError:
            logger.debug("Could not list the fields of %s for the documentation page", name)

        model_classes.append(model_info)

    # Extract standalone functions
    functions = []
    for name, obj in inspect.getmembers(models, inspect.isfunction):
        # Skip private functions
        if name.startswith("_"):
            continue

        # Skip excluded functions
        if name in DOC_CONFIG["excluded_functions"]:
            continue

        # Check for documentation attributes
        if not is_documented(obj, name):
            continue

        functions.append(
            {
                "name": name,
                "docstring": extract_docstring_info(obj),
                "signature": str(inspect.signature(obj)) if hasattr(inspect, "signature") else "",
            }
        )

    context = {
        "models": model_classes,
        "functions": functions,
    }
    return render(request, "nrmps/documentation.html", context)
