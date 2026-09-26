"""Public pages, the simulation list and the simulation page: settings, parameters, populations and runs."""

import json
import logging
from typing import Any, cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.db import DatabaseError, connection, transaction
from django.db.models import F
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django_htmx.http import trigger_client_event
from pydantic import ValidationError

from .exceptions import SimulationError
from .forms import NewSimulationForm, PopulationUploadForm, SimulationForm
from .limits import market_size_error, max_pairs
from .models import PopulationUpload, SavedPreset, Side, Simulation, User, new_seed
from .params import SimulationParams, load_params
from .params_forms import IMPLEMENTED_SECTIONS, ParamsForm
from .pipeline import get_pipeline, needs_run, pipeline_summary
from .population_csv import MAX_UPLOAD_BYTES, MAX_UPLOAD_ROWS, columns, digest, parse_population_csv
from .presets import PRESETS, preset_options, preset_params, resolve_preset, saved_params
from .previews import market_preview
from .quotas import QuotaError, check_preset_quota, check_simulation_quota
from .ratelimit import MESSAGE as RATE_MESSAGE
from .ratelimit import over_limit, rate_limit
from .runs import dispatch_run, start_run

logger = logging.getLogger(__name__)

RECENT_RUNS = 10
# A worker whose heartbeat is older than this counts as missing in /healthz and on the ops page.
WORKER_STALE_SECONDS = 120


def get_owned_simulation(request: HttpRequest, pk: int) -> Simulation:
    """Return the request user's simulation `pk`, or raise Http404 (also for other users' simulations)."""
    return get_object_or_404(Simulation.objects.owned_by(request.user), pk=pk)


def _toast(response: HttpResponse, level: str, text: str) -> HttpResponse:
    """Add a toast to an HTMX response (shown by static/js/site.js)."""
    return trigger_client_event(response, "toast", {"level": level, "text": text})


# --- Public pages -----------------------------------------------------------------------------------------------------


@login_not_required
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
    return JsonResponse({"status": "ok", "tasks": task_health()})


def task_health() -> dict[str, Any]:
    """Describe the background runs: backend, queue and, with a worker, how long ago it was last seen."""
    from .models import SimulationRun, WorkerHeartbeat

    health: dict[str, Any] = {
        "backend": settings.TASK_BACKEND,
        "queued": SimulationRun.objects.filter(status=SimulationRun.Status.QUEUED).count(),
        "running": SimulationRun.objects.filter(status=SimulationRun.Status.RUNNING).count(),
    }
    if settings.TASK_BACKEND == "database":
        last = WorkerHeartbeat.objects.order_by("-last_seen").values_list("last_seen", flat=True).first()
        seconds = None if last is None else round((timezone.now() - last).total_seconds())
        health["worker_last_seen_seconds"] = seconds
        health["worker"] = "ok" if seconds is not None and seconds <= WORKER_STALE_SECONDS else "missing"
    return health


@login_not_required
@require_GET
def index(request):
    """Home page: what the simulator does, the stages of a run, Try a demo, and your recent simulations."""
    recent = _recent_simulations(request.user) if request.user.is_authenticated else []
    return render(request, "nrmps/index.html", {"recent": recent})


def _recent_simulations(user: Any, count: int = 3) -> list[dict[str, Any]]:
    """Return the user's latest simulations, each with its latest run's number and match rate."""
    recent = []
    for sim in Simulation.objects.owned_by(user).with_run_summary().order_by("-id")[:count]:
        latest = sim.latest_run(succeeded=True)
        outcomes = (latest.metrics or {}).get("outcomes") or {} if latest else {}
        recent.append({"sim": sim, "match_rate": (outcomes.get("match") or {}).get("match_rate")})
    return recent


@login_not_required
@require_GET
def contact(request):
    """Contact information page."""
    return render(request, "nrmps/contact.html")


@login_not_required
@require_GET
def privacy(request):
    """Privacy policy page."""
    return render(request, "nrmps/privacy.html")


@login_not_required
@require_GET
def terms(request):
    """Terms of service page."""
    return render(request, "nrmps/terms.html")


# --- Simulations ------------------------------------------------------------------------------------------------------


@require_GET
def simulation_list(request):
    """List the user's simulations (market, state, latest run and match rate) and saved presets."""
    rows = []
    for sim in Simulation.objects.owned_by(request.user).with_run_summary().order_by("-id"):
        try:
            params: SimulationParams | None = sim.get_params()
        except ValidationError:
            params = None
        latest = sim.latest_run(succeeded=True)
        outcomes = ((latest.metrics or {}).get("outcomes") or {}) if latest else {}
        rows.append(
            {
                "sim": sim,
                "market": (params.market.n_applicants, params.n_programs()) if params else None,
                "state": pipeline_summary(get_pipeline(sim)),
                "match_rate": (outcomes.get("match") or {}).get("match_rate"),
            }
        )
    presets = cast(User, request.user).presets.all()
    return render(request, "nrmps/simulations_list.html", {"rows": rows, "saved_presets": presets})


@require_http_methods(["GET", "POST"])
def simulation_create(request):
    """Create a simulation for the current user; it starts with the default parameters and a fresh seed."""
    if request.method == "POST":
        form = NewSimulationForm(request.POST, user=request.user)
        try:
            check_simulation_quota(request.user)
        except QuotaError as exc:
            form.add_error(None, str(exc))
        if form.is_valid():
            sim = form.save(commit=False)
            sim.owner = request.user
            try:
                title, params = resolve_preset(request.user, form.cleaned_data["preset"], new_seed())
            except ValidationError:
                form.add_error("preset", "That saved preset no longer fits the parameters; choose another.")
            else:
                sim.set_params(params)
                sim.save()
                messages.success(
                    request, f"Simulation created from the preset “{title}”. Adjust the parameters or run it."
                )
                return redirect("nrmps:simulation_manage", pk=sim.pk)
    else:
        form = NewSimulationForm(user=request.user)
    chosen = str(form["preset"].value())
    presets = [(option, option.key == chosen) for option in preset_options(request.user)]
    return render(request, "nrmps/simulation_form.html", {"form": form, "create": True, "presets": presets})


def _size_error(params: SimulationParams, simulation: Simulation) -> str | None:
    """Return a message if the market these parameters give is above the size limit (uploads count as they are)."""
    uploads = simulation.uploads_by_side()
    n = uploads["applicants"].rows if "applicants" in uploads else params.market.n_applicants
    m = uploads["programs"].rows if "programs" in uploads else params.n_programs(n)
    return market_size_error(n, m)


def manage_context(request: HttpRequest, sim: Simulation, **overrides) -> dict:
    """Return the context of the simulation page (also used by its HTMX partials)."""
    uploads = sim.uploads_by_side()
    try:
        params = sim.get_params()
    except ValueError:
        params = None
    n = uploads["applicants"].rows if "applicants" in uploads else (params.market.n_applicants if params else 0)
    m = uploads["programs"].rows if "programs" in uploads else (params.n_programs(n) if params else 0)
    stages = get_pipeline(sim)
    context: dict[str, Any] = {
        "simulation": sim,
        "stages": stages,
        "needs_run": needs_run(stages),
        "uploads": uploads,
        "sides": [
            {
                "key": side.value,
                "label": side.label,
                "upload": uploads.get(side.value),
                "columns": columns(params, side.value) if params else [],
                "sample": f"samples/{side.value}_sample.csv",
            }
            for side in Side
        ],
        "market": {"applicants": n, "programs": m, "pairs": n * m},
        "max_pairs": max_pairs(),
        "background": settings.TASK_BACKEND == "database",
        "active_run": sim.active_run(),
        "latest_run": sim.latest_run(),
        "results_run": (results_run := sim.latest_run(succeeded=True)),
        "getting_started": getting_started(sim, results_run),
        "recent_runs": sim.runs.defer("params", "metrics", "fingerprints").annotate(
            match_rate=F("metrics__outcomes__match__match_rate")
        )[:RECENT_RUNS],
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        "max_upload_rows": MAX_UPLOAD_ROWS,
        "upload_errors": {},
        "run_error": None,
    }
    context.update(overrides)
    errors: dict[str, Any] = context["upload_errors"]
    sides: list[dict[str, Any]] = context["sides"]
    for side in sides:
        side["error"] = errors.get(side["key"])
    return context


@require_http_methods(["GET", "POST"])
def simulation_manage(request, pk: int):
    """The simulation page: settings, parameters, populations, the pipeline and the runs."""
    sim = get_owned_simulation(request, pk)
    form = SimulationForm(instance=sim)
    try:
        current = sim.get_params()
    except ValueError:
        current = SimulationParams()
    params_form = ParamsForm(initial=current)

    if request.method == "POST":
        # The page has two forms; each posts a hidden form_id.
        if request.POST.get("form_id") == "params":
            params_form = ParamsForm(request.POST, initial=current)
            if params_form.is_valid() and params_form.params is not None:
                if message := _size_error(params_form.params, sim):
                    params_form.section_errors["market"].append(message)
                else:
                    sim.set_params(params_form.params)
                    sim.save(update_fields=["params", "updated_at"])
                    if "run" in request.POST:
                        if over_limit(request, "run", by="user"):
                            messages.error(request, f"Parameters saved, but not run: {RATE_MESSAGE}")
                            return redirect(reverse("nrmps:simulation_manage", kwargs={"pk": sim.pk}) + "#run")
                        return _run_and_redirect(request, sim)
                    messages.success(request, "Parameters saved.")
                    return redirect(reverse("nrmps:simulation_manage", kwargs={"pk": sim.pk}) + "#run")
            logger.info("Parameters invalid simulation_id=%s", sim.pk)
        elif request.POST.get("form_id") == "preset":
            _apply_preset(request, sim, current)
            return redirect(reverse("nrmps:simulation_manage", kwargs={"pk": sim.pk}) + "#parameters")
        elif request.POST.get("form_id") == "save_preset":
            _save_preset(request, sim)
            return redirect(reverse("nrmps:simulation_manage", kwargs={"pk": sim.pk}) + "#parameters")
        else:
            form = SimulationForm(request.POST, instance=sim)
            if form.is_valid():
                form.save()
                messages.success(request, "Simulation saved.")
                return redirect("nrmps:simulation_manage", pk=sim.pk)
            logger.info("Simulation form invalid simulation_id=%s fields=%s", sim.pk, sorted(form.errors))

    context = manage_context(request, sim, form=form, params_form=params_form)
    options = preset_options(request.user)
    context["builtin_presets"] = [option for option in options if not option.own]
    context["own_presets"] = [option for option in options if option.own]
    context["preview"] = market_preview(current, sim.uploads_by_side())
    warnings = current.warnings() if not params_form.is_bound else []
    implemented = set(IMPLEMENTED_SECTIONS)
    context["param_warnings"] = [w for w in warnings if w.path.split(".")[0] in implemented]
    context["planned_warnings"] = [w for w in warnings if w.path.split(".")[0] not in implemented]
    return render(request, "nrmps/simulation_manage.html", context)


# The presets offered by "Try a demo", first the default.
DEMO_PRESETS = ("nrmp_like", "classroom", "signals")


@require_http_methods(["GET", "POST"])
def demo(request):
    """Try a demo: create a simulation from a preset, run it, and open its results (GET explains and asks)."""
    if request.method == "GET":
        return render(request, "nrmps/demo.html", {"presets": [(key, PRESETS[key]) for key in DEMO_PRESETS]})
    key = request.POST.get("preset", DEMO_PRESETS[0])
    key = key if key in DEMO_PRESETS else DEMO_PRESETS[0]
    try:
        check_simulation_quota(request.user)
    except QuotaError as exc:
        messages.error(request, str(exc))
        return redirect("nrmps:simulation_list")
    if over_limit(request, "run", by="user"):
        messages.error(request, RATE_MESSAGE)
        return redirect("nrmps:simulation_list")
    preset = PRESETS[key]
    sim = Simulation(owner=request.user, name=f"Demo: {preset.title}", description=preset.description)
    sim.set_params(preset_params(key, seed=new_seed()))
    sim.save()
    return _run_and_redirect(request, sim)


def getting_started(sim: Simulation, results_run: Any) -> list[dict[str, Any]] | None:
    """Return the getting-started checklist of a simulation, or None once it has two successful runs."""
    succeeded = sim.runs.filter(status="succeeded").count()
    if succeeded >= 2:
        return None
    results = reverse("nrmps:run_detail", kwargs={"pk": sim.pk, "number": results_run.number}) if results_run else ""
    return [
        {"text": "Choose the parameters, or keep the preset's", "done": True, "url": "#parameters"},
        {"text": "Run the simulation", "done": sim.runs.exists(), "url": "#run"},
        {
            "text": "Explore the results: the match, the funnel, each applicant's path",
            "done": succeeded >= 1,
            "url": results,
        },
        {"text": "Change a parameter and run again to compare", "done": succeeded >= 2, "url": "#parameters"},
    ]


@require_POST
def params_preview(request, pk: int):
    """The preview panel for the parameters as edited (HTMX, not saved): the market they give and its pictures."""
    sim = get_owned_simulation(request, pk)
    try:
        current = sim.get_params()
    except ValueError:
        current = SimulationParams()
    form = ParamsForm(request.POST, initial=current)
    context: dict[str, Any] = {"simulation": sim, "preview": None, "preview_errors": []}
    if form.is_valid() and form.params is not None:
        context["preview"] = market_preview(form.params, sim.uploads_by_side())
    else:
        context["preview_errors"] = [f"{label}: {message}" for _anchor, label, message in form.error_summary()][:5]
    return render(request, "nrmps/partials/_params_preview.html", context)


def _apply_preset(request: HttpRequest, sim: Simulation, current: SimulationParams) -> None:
    """Replace the simulation's parameters with a preset's (built in or saved), keeping the seed."""
    seed = current.run.seed if current.run.seed is not None else new_seed()
    try:
        title, params = resolve_preset(request.user, request.POST.get("preset", ""), seed)
    except KeyError:
        messages.error(request, "Choose one of the presets.")
        return
    except ValidationError:
        messages.error(request, "That saved preset no longer fits the parameters; delete it and save it again.")
        return
    if message := _size_error(params, sim):
        messages.error(request, f"The preset was not applied: {message}")
        return
    sim.set_params(params)
    sim.save(update_fields=["params", "updated_at"])
    messages.success(request, f"Applied the preset “{title}”: every parameter now comes from it (the seed is kept).")


def _save_preset(request: HttpRequest, sim: Simulation) -> None:
    """Save the simulation's saved parameters (without the seed) as a preset of the user's."""
    user = cast(User, request.user)  # every page but the public ones requires login
    name = request.POST.get("name", "").strip()[:100]
    description = request.POST.get("description", "").strip()[:300]
    if not name:
        messages.error(request, "Give the preset a name.")
        return
    if user.presets.filter(name=name).exists():
        messages.error(request, f"You already have a preset called “{name}”. Choose another name, or delete it first.")
        return
    try:
        check_preset_quota(user)
        params = sim.get_params()
    except QuotaError as exc:
        messages.error(request, str(exc))
        return
    except ValidationError:
        messages.error(request, "The saved parameters are not valid. Fix them and save them first.")
        return
    SavedPreset.objects.create(owner=user, name=name, description=description, params=saved_params(params))
    messages.success(request, f"Saved the parameters as the preset “{name}”; new simulations can start from it.")


@require_POST
def simulation_duplicate(request, pk: int):
    """Copy a simulation: its details, parameters (with the seed) and uploaded populations, but not its runs."""
    sim = get_owned_simulation(request, pk)
    try:
        check_simulation_quota(request.user)
    except QuotaError as exc:
        messages.error(request, str(exc))
        return redirect("nrmps:simulation_list")
    with transaction.atomic():
        copy = Simulation.objects.create(
            owner=request.user, name=f"Copy of {sim.name}"[:255], description=sim.description, params=sim.params
        )
        for upload in sim.uploads.all():
            upload.pk = None
            upload.simulation = copy
            upload.save()
    messages.success(request, f"Duplicated “{sim.name}”: the same parameters, seed and uploaded files; no runs yet.")
    return redirect("nrmps:simulation_manage", pk=copy.pk)


MAX_PARAMS_FILE_BYTES = 100_000


@require_GET
def params_export(request, pk: int):
    """Download the simulation's saved parameters as JSON, the format the parameters upload reads."""
    sim = get_owned_simulation(request, pk)
    body = json.dumps(sim.params, indent=2, sort_keys=True) + "\n"
    response = HttpResponse(body, content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{slugify(sim.name) or "simulation"}-parameters.json"'
    return response


@require_POST
def params_import(request, pk: int):
    """Replace the simulation's parameters with a JSON file's (a parameters download, or a run's params.json)."""
    sim = get_owned_simulation(request, pk)
    target = reverse("nrmps:simulation_manage", kwargs={"pk": sim.pk}) + "#parameters"
    upload = request.FILES.get("file")
    if upload is None or upload.size > MAX_PARAMS_FILE_BYTES:
        messages.error(request, f"Choose a parameters JSON file of at most {MAX_PARAMS_FILE_BYTES // 1000} kB.")
        return redirect(target)
    try:
        data = json.loads(upload.read().decode("utf-8"))
        params = load_params(data)
    except UnicodeDecodeError, json.JSONDecodeError:
        messages.error(request, "The file is not JSON. Upload a parameters file downloaded from this site.")
        return redirect(target)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:3])
        messages.error(request, f"The parameters in the file are not valid: {problems}.")
        return redirect(target)
    if params.run.seed is None:
        params = params.with_seed(sim.get_params().run.seed)
    if message := _size_error(params, sim):
        messages.error(request, f"The parameters were not loaded: {message}")
        return redirect(target)
    sim.set_params(params)
    sim.save(update_fields=["params", "updated_at"])
    messages.success(request, f"Loaded the parameters from {upload.name}.")
    return redirect(target)


@require_POST
def preset_delete(request, preset_id: int):
    """Delete one of the user's saved presets."""
    preset = get_object_or_404(SavedPreset, pk=preset_id, owner=request.user)
    preset.delete()
    messages.success(request, f"Deleted the preset “{preset.name}”.")
    return redirect("nrmps:simulation_list")


def _run_and_redirect(request: HttpRequest, sim: Simulation) -> HttpResponse:
    """Run the simulation (no JavaScript, or "Save and run") and redirect to the result."""
    try:
        run = dispatch_run(start_run(sim, request.user, notify=request.POST.get("notify") == "on"))
    except SimulationError as exc:
        messages.error(request, str(exc))
        return redirect(reverse("nrmps:simulation_manage", kwargs={"pk": sim.pk}) + "#run")
    if run.status == run.Status.SUCCEEDED:
        messages.success(request, f"Run {run.number} finished.")
    elif run.status == run.Status.FAILED:
        messages.error(request, f"Run {run.number} failed: {run.error}")
    else:
        messages.info(request, f"Run {run.number} is queued; this page shows its progress.")
    return redirect("nrmps:run_detail", pk=sim.pk, number=run.number)


@require_POST
def simulation_delete(request, pk: int):
    """Delete a simulation with everything in it."""
    sim = get_owned_simulation(request, pk)
    name = sim.name
    sim.delete()
    messages.success(request, f"Deleted the simulation “{name}”.")
    return redirect("nrmps:simulation_list")


# --- Runs (HTMX from the simulation page) -----------------------------------------------------------------------------


def _run_panel(request: HttpRequest, sim: Simulation, **overrides) -> HttpResponse:
    """Render the run panel and, out of band, the stepper."""
    context = manage_context(request, sim, **overrides)
    panel = render(request, "nrmps/partials/_run_panel.html", context).content.decode()
    stepper = render(request, "nrmps/partials/_pipeline.html", context | {"oob": True}).content.decode()
    return HttpResponse(panel + stepper)


def _finished_toast(response: HttpResponse, run) -> HttpResponse:
    if run.status == run.Status.SUCCEEDED:
        return _toast(response, "success", f"Run {run.number} finished.")
    return _toast(response, "error", f"Run {run.number} failed: {run.error}")


@require_POST
@rate_limit("run", by="user")
def run_start(request, pk: int):
    """Run the simulation with its saved parameters: now, or in the background when a worker executes runs."""
    sim = get_owned_simulation(request, pk)
    if not request.htmx:
        return _run_and_redirect(request, sim)
    try:
        run = dispatch_run(start_run(sim, request.user, notify=request.POST.get("notify") == "on"))
    except SimulationError as exc:
        return _toast(_run_panel(request, sim, run_error=str(exc)), "error", str(exc))
    if run.is_active:
        return _toast(_run_panel(request, sim), "info", f"Run {run.number} is queued.")
    return _finished_toast(_run_panel(request, sim), run)


@require_GET
def run_status(request, pk: int):
    """The run panel again, for polling while a run is queued or running; says so when the awaited run finished."""
    sim = get_owned_simulation(request, pk)
    response = _run_panel(request, sim)
    awaited = request.GET.get("run", "")
    if awaited.isdigit():
        run = sim.runs.filter(number=int(awaited)).first()
        if run is not None and not run.is_active:
            return _finished_toast(response, run)
    return response


# --- Uploads (HTMX from the simulation page) --------------------------------------------------------------------------


def _population_card(request: HttpRequest, sim: Simulation, side: str, **overrides) -> HttpResponse:
    """Render one side's population card and, out of band, the stepper."""
    context = manage_context(request, sim, **overrides)
    context["side"] = next(entry for entry in context["sides"] if entry["key"] == side)
    card = render(request, "nrmps/partials/_population_side.html", context).content.decode()
    stepper = render(request, "nrmps/partials/_pipeline.html", context | {"oob": True}).content.decode()
    return HttpResponse(card + stepper)


def _side(side: str) -> str:
    if side not in Side.values:
        raise Http404("Unknown side")
    return side


@require_POST
@rate_limit("upload", by="user")
def population_upload(request, pk: int, side: str):
    """Replace one side's population with an uploaded CSV, validated in memory before anything is stored."""
    sim = get_owned_simulation(request, pk)
    side = _side(side)
    label = Side(side).label.lower()
    form = PopulationUploadForm(request.POST, request.FILES)
    try:
        if not form.is_valid():
            raise SimulationError("Choose a CSV file to upload.")
        params = sim.get_params()
        upload = parse_population_csv(form.cleaned_data["file"], side, params)
        other = "programs" if side == "applicants" else "applicants"
        others = sim.uploads_by_side().get(other)
        n = upload.rows if side == "applicants" else (others.rows if others else params.market.n_applicants)
        m = upload.rows if side == "programs" else (others.rows if others else params.n_programs(n))
        if message := market_size_error(n, m):
            raise SimulationError(message)
    except SimulationError as exc:
        details = getattr(exc, "details", [])
        response = _population_card(request, sim, side, upload_errors={side: {"message": str(exc), "details": details}})
        return _toast(response, "error", str(exc))
    data = upload.to_npz()
    with transaction.atomic():
        sim.lock()
        PopulationUpload.objects.update_or_create(
            simulation=sim,
            side=side,
            defaults={
                "filename": form.cleaned_data["file"].name[:255],
                "rows": upload.rows,
                "data": data,
                "digest": digest(data),
            },
        )
    response = _population_card(request, sim, side)
    return _toast(response, "success", f"Loaded {upload.rows:,} {label} from the file. Runs now use them.")


@require_POST
def population_upload_remove(request, pk: int, side: str):
    """Go back to generating one side's population from the parameters."""
    sim = get_owned_simulation(request, pk)
    side = _side(side)
    sim.uploads.filter(side=side).delete()
    response = _population_card(request, sim, side)
    return _toast(response, "success", f"Runs now generate the {Side(side).label.lower()} from the parameters.")
