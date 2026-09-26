"""Pages of one run: summary and diagnostics, applicants, programs, one agent's view, and downloads."""

import json
from collections.abc import Iterator
from typing import Any

import numpy as np
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from .engine.numeric import quantiles
from .engine.pipeline import SideResult
from .models import SimulationRun
from .params_forms import ParamsForm
from .population_csv import plain_csv_lines, population_csv_lines
from .runs import PAIR_COLUMNS, RunData
from .views import get_owned_simulation

PAGE_SIZES = [25, 50, 100, 200, 500]


def get_run(request: HttpRequest, pk: int, number: int) -> SimulationRun:
    """Return run `number` of the user's simulation `pk`, or raise Http404."""
    sim = get_owned_simulation(request, pk)
    return get_object_or_404(sim.runs.select_related("simulation"), number=number)


def _finished_data(run: SimulationRun) -> tuple[RunData, SideResult, SideResult]:
    """Return a successful run's data and its applicant and program results, or raise Http404."""
    if run.status != SimulationRun.Status.SUCCEEDED:
        raise Http404("The run has no results")
    data = RunData(run)
    if data.applicant_results is None or data.program_results is None:
        raise Http404("The run has no results")
    return data, data.applicant_results, data.program_results


def _page_size(request: HttpRequest) -> int:
    """Return the requested page size if it is one of the offered sizes, else 100."""
    try:
        size = int(request.GET.get("page_size", 100))
    except TypeError, ValueError:
        return 100
    return size if size in PAGE_SIZES else 100


def _paginate(request: HttpRequest, items: list[Any], page_size: int) -> dict[str, Any]:
    """Return the page_obj and the elided page_range for a list page."""
    paginator = Paginator(items, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    return {
        "page_obj": page_obj,
        "page_range": list(paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)),
        "page_size": page_size,
        "page_sizes": PAGE_SIZES,
    }


def _order(request: HttpRequest, keys: dict[str, np.ndarray | list[Any]], default: str) -> tuple[list[int], str, str]:
    """Return the row order for the requested sort key and direction (ties by index), with the key and direction."""
    sort = request.GET.get("sort", default)
    if sort not in keys:
        sort = default
    order = "desc" if request.GET.get("order") == "desc" else "asc"
    values = keys[sort]
    indices = sorted(range(len(values)), key=lambda i: (values[i], i), reverse=order == "desc")
    return indices, sort, order


def _chips(keys: tuple[str, ...], values: np.ndarray) -> list[tuple[str, float]]:
    return [(key, float(value)) for key, value in zip(keys, values, strict=True)]


# --- Summary ----------------------------------------------------------------------------------------------------------


def _param_groups(run: SimulationRun) -> list[dict[str, Any]]:
    """Return the run's implemented parameters grouped by section, for display."""
    form = ParamsForm(initial=run.get_params())
    groups = []
    for section in form.sections():
        scalars = [(bound.label, bound.value()) for bound in section.fields + section.advanced_fields]
        lists = [
            {
                "title": view.spec.title,
                "columns": [column.title for column in view.spec.columns if column.implemented],
                "rows": [
                    [form_.initial.get(column.path) for column in view.spec.columns if column.implemented]
                    for form_ in view.formset.forms
                ],
            }
            for view in section.lists
        ]
        groups.append({"title": section.title, "scalars": scalars, "lists": lists})
    return groups


HISTOGRAM_TITLES = {
    "strength": "Applicant strength",
    "quality": "Program quality",
    "capacity": "Positions per program",
    "applicant_fidelity": "Applicants' pre-interview fidelity",
    "program_fidelity": "Programs' pre-interview fidelity",
}


def _histograms(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the run's histograms with bar heights relative to the tallest bin."""
    result = []
    for key, title in HISTOGRAM_TITLES.items():
        histogram = (metrics.get("histograms") or {}).get(key)
        if not histogram:
            continue
        edges, counts = histogram["edges"], histogram["counts"]
        peak = max(counts) or 1
        bins = [
            {"low": low, "high": high, "count": count, "height": round(100 * count / peak)}
            for low, high, count in zip(edges[:-1], edges[1:], counts, strict=True)
        ]
        result.append({"key": key, "title": title, "bins": bins, "low": edges[0], "high": edges[-1], "peak": peak})
    return result


@require_GET
def run_detail(request, pk: int, number: int):
    """A run: status, version stamps, parameters and the pre-interview diagnostics."""
    run = get_run(request, pk, number)
    context = {
        "simulation": run.simulation,
        "run": run,
        "stages": run.stages.order_by("id"),
        "metrics": run.metrics or {},
        "param_groups": _param_groups(run),
        "stamps": run.stamps(),
        "histograms": _histograms(run.metrics or {}),
        "pairs_download": run.n_pairs <= settings.NRMP_DRILLDOWN_MAX_PAIRS,
    }
    return render(request, "nrmps/runs/run_detail.html", context)


@require_GET
def run_progress(request, pk: int, number: int):
    """The progress block of a queued or running run (polled); once the run has finished, reload the page."""
    run = get_run(request, pk, number)
    if run.is_active:
        return render(request, "nrmps/runs/_progress.html", {"simulation": run.simulation, "run": run})
    response = HttpResponse("")
    response["HX-Refresh"] = "true"
    return response


@require_POST
def run_delete(request, pk: int, number: int):
    """Delete a run and its results."""
    run = get_run(request, pk, number)
    if run.is_active:
        messages.error(request, f"Run {run.number} is still in progress; it cannot be deleted yet.")
        return redirect("nrmps:run_detail", pk=pk, number=number)
    run.delete()
    messages.success(request, f"Deleted run {number}.")
    return redirect("nrmps:simulation_manage", pk=pk)


# --- Agents -----------------------------------------------------------------------------------------------------------


@require_GET
def run_applicants(request, pk: int, number: int):
    """The run's applicants with their attributes, weights and pre-interview results."""
    run = get_run(request, pk, number)
    data, results, programs = _finished_data(run)
    a, p = data.population.applicants, data.population.programs
    percentile = quantiles(a.strength) * 100
    keys = {
        "index": list(range(a.size)),
        "name": [a.name(i) for i in range(a.size)],
        "group": [a.group_names[g] for g in a.group],
        "strength": a.strength.tolist(),
        "fidelity": np.nan_to_num(results.fidelity, nan=-2.0).tolist(),
        "popularity": programs.popularity.tolist(),
    }
    indices, sort, order = _order(request, keys, "index")
    context = {
        "simulation": run.simulation,
        "run": run,
        "sort": sort,
        "order": order,
        **_paginate(request, indices, _page_size(request)),
    }
    context["rows"] = [
        {
            "number": i + 1,
            "name": a.name(i),
            "group": a.group_names[a.group[i]],
            "strength": a.strength[i],
            "percentile": percentile[i],
            "attributes": _chips(a.keys, a.attributes[i]),
            "weights": _chips(a.weight_keys, a.weights[i]),
            "first_choice": int(results.first_choice[i]) + 1,
            "first_choice_name": p.name(int(results.first_choice[i])),
            "fidelity": results.fidelity[i],
            "popularity": int(programs.popularity[i]),
        }
        for i in context["page_obj"].object_list
    ]
    return render(request, "nrmps/runs/applicants_list.html", context)


@require_GET
def run_programs(request, pk: int, number: int):
    """The run's programs with their attributes, weights, capacity and pre-interview results."""
    run = get_run(request, pk, number)
    data, applicants, results = _finished_data(run)
    a, p = data.population.applicants, data.population.programs
    percentile = quantiles(p.quality) * 100
    keys = {
        "index": list(range(p.size)),
        "name": [p.name(j) for j in range(p.size)],
        "tier": [p.tier_names[t] for t in p.tier],
        "quality": p.quality.tolist(),
        "capacity": p.capacity.tolist(),
        "fidelity": np.nan_to_num(results.fidelity, nan=-2.0).tolist(),
        "popularity": applicants.popularity.tolist(),
    }
    indices, sort, order = _order(request, keys, "index")
    context = {
        "simulation": run.simulation,
        "run": run,
        "sort": sort,
        "order": order,
        **_paginate(request, indices, _page_size(request)),
    }
    context["rows"] = [
        {
            "number": j + 1,
            "name": p.name(j),
            "tier": p.tier_names[p.tier[j]],
            "quality": p.quality[j],
            "percentile": percentile[j],
            "capacity": int(p.capacity[j]),
            "attributes": _chips(p.keys, p.attributes[j]),
            "weights": _chips(p.weight_keys, p.weights[j]),
            "first_choice": int(results.first_choice[j]) + 1,
            "first_choice_name": a.name(int(results.first_choice[j])),
            "fidelity": results.fidelity[j],
            "popularity": int(applicants.popularity[j]),
        }
        for j in context["page_obj"].object_list
    ]
    return render(request, "nrmps/runs/programs_list.html", context)


def _agent_page(request: HttpRequest, pk: int, number: int, index: int, *, applicant: bool) -> HttpResponse:
    run = get_run(request, pk, number)
    data, _applicants, _programs = _finished_data(run)
    population = data.population
    me_side = population.applicants if applicant else population.programs
    other_side = population.programs if applicant else population.applicants
    if not 1 <= index <= me_side.size:
        raise Http404("No such agent")
    agent = index - 1
    rows = data.applicant_rows(agent) if applicant else data.program_rows(agent)
    keys = {
        "pre_rank": rows.observed_rank.tolist(),
        "true_rank": rows.true_rank.tolist(),
        "name": [other_side.name(t) for t in range(other_side.size)],
        "index": list(range(other_side.size)),
    }
    if rows.other_observed_rank is not None and rows.other_true_rank is not None:
        keys["their_pre_rank"] = rows.other_observed_rank.tolist()
        keys["their_true_rank"] = rows.other_true_rank.tolist()
    indices, sort, order = _order(request, keys, "pre_rank")
    context = {
        "simulation": run.simulation,
        "run": run,
        "applicant": applicant,
        "index": index,
        "name": me_side.name(agent),
        "sort": sort,
        "order": order,
        "has_their_ranks": rows.other_observed_rank is not None,
        **_paginate(request, indices, _page_size(request)),
    }
    context["rows"] = [
        {
            "number": t + 1,
            "name": other_side.name(t),
            "true": rows.true[t],
            "observed": rows.observed[t],
            "true_rank": int(rows.true_rank[t]),
            "pre_rank": int(rows.observed_rank[t]),
            "their_true": rows.other_true[t],
            "their_observed": rows.other_observed[t],
            "their_true_rank": int(rows.other_true_rank[t]) if rows.other_true_rank is not None else None,
            "their_pre_rank": int(rows.other_observed_rank[t]) if rows.other_observed_rank is not None else None,
        }
        for t in context["page_obj"].object_list
    ]
    return render(request, "nrmps/runs/agent_detail.html", context)


@require_GET
def run_applicant(request, pk: int, number: int, index: int):
    """One applicant's view of every program before interviews, and every program's view of the applicant."""
    return _agent_page(request, pk, number, index, applicant=True)


@require_GET
def run_program(request, pk: int, number: int, index: int):
    """One program's view of every applicant before interviews, and every applicant's view of the program."""
    return _agent_page(request, pk, number, index, applicant=False)


# --- Downloads --------------------------------------------------------------------------------------------------------


def _attachment[R: HttpResponse | StreamingHttpResponse](response: R, filename: str) -> R:
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()


@require_GET
def run_download(request, pk: int, number: int, name: str):
    """Download a run's applicants or programs (the upload format), pairs, metrics or parameters."""
    run = get_run(request, pk, number)
    prefix = f"{slugify(run.simulation.name) or 'simulation'}-run-{run.number}"
    if name == "params.json":
        response = HttpResponse(_json_bytes(run.params), content_type="application/json")
        return _attachment(response, f"{prefix}-params.json")
    if name == "metrics.json":
        record = {
            "simulation": run.simulation.name,
            "run": run.number,
            "status": run.status,
            "seed": run.seed,
            "params_hash": run.params_hash,
            "population_digest": run.population_digest,
            "population_source": run.population_source,
            "stamps": run.stamps(),
            "duration_ms": run.duration_ms,
            "metrics": run.metrics,
        }
        return _attachment(HttpResponse(_json_bytes(record), content_type="application/json"), f"{prefix}-metrics.json")
    data, _applicants, _programs = _finished_data(run)
    lines: Iterator[str]
    if name == "applicants.csv":
        lines = population_csv_lines(data.population.applicants)
    elif name == "programs.csv":
        lines = population_csv_lines(data.population.programs)
    elif name == "pairs.csv":
        if not data.drilldown_ranks:
            raise Http404("This run is too large for the pairs file")
        lines = plain_csv_lines(PAIR_COLUMNS, data.pair_rows())
    else:
        raise Http404("Unknown download")
    return _attachment(StreamingHttpResponse(lines, content_type="text/csv; charset=utf-8"), f"{prefix}-{name}")
