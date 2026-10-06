"""Pages of one run, and the comparison of two runs.

A run's pages: summary, outcomes and diagnostics, applicants, programs, one agent's view, and downloads.
"""

import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import cached_property
from typing import Any
from urllib.parse import urlencode

import numpy as np
from django.conf import settings
from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from .charts import TAB_CHARTS, agent_funnel, ego_network, run_charts
from .compare import comparison_charts, key_numbers, pairing, parameter_differences, same_setup
from .engine.numeric import quantiles
from .engine.persistence import StageRecord
from .engine.pipeline import SideResult
from .engine.validate import COUNT_CHECKS, FLAG_CHECKS
from .examples import Example, SavedRun
from .exceptions import SimulationError
from .models import IMPLEMENTED_STAGES, RunArtifact, SimulationRun, StageRun
from .params_forms import ParamsForm
from .population_csv import plain_csv_lines, population_csv_lines
from .ratelimit import rate_limit
from .runs import (
    APPLICATION_COLUMNS,
    MATCH_COLUMNS,
    PAIR_COLUMNS,
    PROGRAM_RESULT_COLUMNS,
    PairRows,
    RunData,
    StageRows,
    dispatch_run,
    run_wait,
    start_run,
)
from .views import get_owned_simulation

PAGE_SIZES = [25, 50, 100, 200, 500]
PUBLIC_PAGE_SIZES = [25, 50, 100]  # of a saved example's tables: anyone can ask for them, so pages stay light


def get_run(request: HttpRequest, pk: int, number: int) -> SimulationRun:
    """Return run `number` of the user's simulation `pk`, or raise Http404."""
    sim = get_owned_simulation(request, pk)
    return get_object_or_404(sim.runs.select_related("simulation"), number=number)


@dataclass
class RunPages:
    """The run that a page shows and where its pages are: a user's run, or a saved example run (nrmps.examples).

    The page functions below (summary_page, population_page ...) render either one with the same templates: a user's
    run from the database, with the buttons that change it, or an example from its files, read-only and for everyone.
    """

    run: SimulationRun
    saved: SavedRun | None = None

    @property
    def example(self) -> Example | None:
        """Return the example the pages belong to, or None for a user's run."""
        return self.saved.example if self.saved is not None else None

    @cached_property
    def data(self) -> RunData:
        """Return the run's data, loaded once for the page."""
        return self.saved.data if self.saved is not None else RunData(self.run)

    def finished(self) -> tuple[RunData, SideResult, SideResult]:
        """Return a successful run's data and its applicant and program results, or raise Http404."""
        if self.run.status != SimulationRun.Status.SUCCEEDED:
            raise Http404("The run has no results")
        data = self.data
        if data.applicant_results is None or data.program_results is None:
            raise Http404("The run has no results")
        return data, data.applicant_results, data.program_results

    def charts(self, names: tuple[str, ...]) -> dict[str, Any]:
        """Return the charts `names` of the run (an example keeps them: its run never changes)."""
        return self.saved.charts(names) if self.saved is not None else run_charts(self.data, names)

    def url(self, page: str, /, **kwargs: Any) -> str:
        """Return the address of the run's page `page`: "detail", "match", "applicant" (with index=) ..."""
        if self.saved is not None:
            return reverse(f"nrmps:example_{page}", kwargs={"slug": self.saved.example.slug, **kwargs})
        return reverse(f"nrmps:run_{page}", kwargs={"pk": self.run.simulation_id, "number": self.run.number, **kwargs})

    def stage_records(self) -> Iterable[StageRun]:
        """Return the records of the stages that ran."""
        return self.saved.stages if self.saved is not None else self.run.stages.all()

    def has_stage_results(self) -> bool:
        """Return True if the run stored the decisions from applications to the match."""
        if self.saved is not None:
            return self.saved.data.stages is not None
        return self.run.artifacts.filter(kind=RunArtifact.Kind.STAGES).exists()

    @property
    def pairs_download(self) -> bool:
        """Return True if the pairs file (a row per applicant and program) is offered: not for a large market."""
        small = self.run.n_pairs <= settings.NRMP_DRILLDOWN_MAX_PAIRS
        return small and (self.saved is None or self.saved.pairs_download)

    @property
    def page_sizes(self) -> list[int]:
        """Return the rows per page that the run's tables offer."""
        return PAGE_SIZES if self.saved is None else PUBLIC_PAGE_SIZES


def _page_size(request: HttpRequest, sizes: list[int]) -> int:
    """Return the requested page size if it is one of the offered `sizes`, else 100."""
    try:
        size = int(request.GET.get("page_size", 100))
    except TypeError, ValueError:
        return 100
    return size if size in sizes else 100


def _paginate(request: HttpRequest, items: list[Any] | np.ndarray, sizes: list[int]) -> dict[str, Any]:
    """Return the page_obj and the elided page_range for a list page, with the rows per page out of `sizes`."""
    page_size = _page_size(request, sizes)
    paginator = Paginator(items, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    return {
        "page_obj": page_obj,
        "page_range": list(paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)),
        "page_size": page_size,
        "page_sizes": sizes,
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


UNRANKED = 10**9  # sort key of entries not on a list: after every rank


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


# Readable names of the counts the stages record.
COUNT_LABELS = {
    "applicant_entries": "applicant list entries",
    "program_entries": "program list entries",
    "blocking_pairs": "blocking pairs",
}


def _stage_rows(run: SimulationRun, records: Iterable[StageRun] | None = None) -> list[dict[str, Any]]:
    """Return every stage of the run in order: its status, time and counts in words.

    A stage without a record is waiting while the run is queued or running (the first one of a running run is in
    progress), and was not run if the run failed before it (or is from before the stage existed). `records` are the
    stage records to use instead of the run's own in the database (a saved example's).
    """
    recorded = {stage.stage: stage for stage in (run.stages.all() if records is None else records)}
    in_progress = run.status == SimulationRun.Status.RUNNING
    rows = []
    for stage in IMPLEMENTED_STAGES:
        record = recorded.get(stage.value)
        if record is not None:
            counts = ", ".join(f"{intcomma(n)} {COUNT_LABELS.get(key, key)}" for key, n in record.counts.items())
            rows.append(
                {
                    "label": stage.label,
                    "status": record.status,
                    "duration_ms": record.duration_ms,
                    "result": record.error or counts,
                }
            )
        elif in_progress:
            rows.append({"label": stage.label, "status": "running", "duration_ms": None, "result": "In progress"})
            in_progress = False
        else:
            status = "waiting" if run.is_active else "not_run"
            rows.append({"label": stage.label, "status": status, "duration_ms": None, "result": ""})
    return rows


def _outcomes(metrics: dict[str, Any]) -> dict[str, Any] | None:
    """Return the checks and the group tables (None for runs from before the match)."""
    outcomes = metrics.get("outcomes")
    if not outcomes:
        return None
    checks = outcomes.get("checks") or {}
    rows = [
        {"title": title, "value": checks.get(key), "ok": checks.get(key) == 0} for key, title in COUNT_CHECKS.items()
    ]
    for key, title in FLAG_CHECKS.items():
        value = checks.get(key)
        rows.append({"title": title, "value": value, "ok": value is not False, "skipped": value is None})
    group_tables = [
        ("By applicant group", outcomes["by_group"], "Group"),
        ("By strength decile", outcomes["by_strength_decile"], "Decile"),
    ]
    return {"checks": rows, "passed": checks.get("passed"), "group_tables": group_tables}


def _number(value: float | None, digits: int) -> str:
    """Return a number with `digits` decimals and thousands separators, or "-" when there is none."""
    return "-" if value is None else f"{value:,.{digits}f}"


def _source(label: str | None) -> str:
    """Return where a side of the population comes from, in words."""
    return "generated" if label in {None, "generated"} else f"uploaded ({label})"


# The tabs of a run's pages: key, label and the page's name (RunPages.url).
RUN_TABS = [
    ("summary", "Summary", "detail"),
    ("population", "Population", "population"),
    ("pre_interview", "Before interviews", "pre_interview"),
    ("applications", "Applications and interviews", "applications"),
    ("match", "Match", "match"),
    ("applicants", "Applicants", "applicants"),
    ("programs", "Programs", "programs"),
]
OUTCOME_TABS = {"applications", "match"}  # only for runs that went on to the match


def _run_context(pages: RunPages, tab: str, **extra: Any) -> dict[str, Any]:
    """Return the context every page of a run shares: the run, its diagnostics and the tabs."""
    run = pages.run
    metrics = run.metrics or {}
    outcomes = metrics.get("outcomes")
    labels = {key: label for key, label, _name in RUN_TABS}
    tabs = []
    if run.status == SimulationRun.Status.SUCCEEDED:
        tabs = [
            {"key": key, "label": label, "url": pages.url(name)}
            for key, label, name in RUN_TABS
            if outcomes or key not in OUTCOME_TABS
        ]
    return {
        "simulation": run.simulation,
        "run": run,
        "pages": pages,
        "example": pages.example,
        "tab": tab,
        "tab_label": "" if tab == "summary" else labels[tab],
        "help_page": "example_summary" if pages.saved is not None and tab == "summary" else f"run_{tab}",
        "tabs": tabs,
        "metrics": metrics,
        "outcomes": outcomes,
        "wait": run_wait(run) if run.is_active else None,
        **extra,
    }


def highlights(pages: RunPages) -> list[dict[str, str]]:
    """Return what to look at in a saved example: the pages it points to, with their labels and addresses."""
    example = pages.example
    if example is None:
        return []
    tabs = {key: (label, name) for key, label, name in RUN_TABS}
    return [{"label": tabs[key][0], "url": pages.url(tabs[key][1]), "text": text} for key, text in example.highlights]


@require_GET
def run_detail(request, pk: int, number: int):
    """A run's summary: status, key numbers, the applicants' flow, downloads, stages, checks and parameters."""
    return summary_page(request, RunPages(get_run(request, pk, number)))


def summary_page(request: HttpRequest, pages: RunPages) -> HttpResponse:
    """Render the summary of a user's run, or of a saved example."""
    run = pages.run
    stage_results = pages.has_stage_results()
    # Who gets an interview and a match (the Applications and interviews tab's flow), split by strength from the start.
    charts = {}
    if run.status == SimulationRun.Status.SUCCEEDED and stage_results:
        charts = pages.charts(("applicant_flow",))
    context = _run_context(
        pages,
        "summary",
        charts={name: chart for name, chart in charts.items() if chart},
        stage_rows=_stage_rows(run, pages.stage_records()),
        outcome_views=_outcomes(run.metrics or {}),
        param_groups=_param_groups(run),
        pairs_download=pages.pairs_download,
        stage_downloads=stage_results,
        highlights=highlights(pages),
    )
    return render(request, "nrmps/runs/run_detail.html", context)


@require_GET
def run_population(request, pk: int, number: int):
    """The population of a run: the market as generated against the request, with its distributions."""
    return population_page(request, RunPages(get_run(request, pk, number)))


def population_page(request: HttpRequest, pages: RunPages) -> HttpResponse:
    """Render the population of a user's run, or of a saved example."""
    run = pages.run
    pages.finished()
    market = (run.metrics or {}).get("market") or {}
    capacity = market.get("capacity") or {}
    sources = run.population_source
    stats = [
        ("Applicants", intcomma(run.n_applicants), _source(sources.get("applicants"))),
        ("Programs", intcomma(run.n_programs), _source(sources.get("programs"))),
        (
            "Positions",
            intcomma(run.n_positions),
            f"{_number(market.get('applicants_per_position'), 3)} applicants per position",
        ),
        (
            "Positions per program",
            _number(capacity.get("median"), 1),
            f"median; {capacity.get('min', '-')} to {capacity.get('max', '-')}",
        ),
    ]
    context = _run_context(pages, "population", stats=stats, charts=pages.charts(TAB_CHARTS["population"]))
    return render(request, "nrmps/runs/population.html", context)


@require_GET
def run_pre_interview(request, pk: int, number: int):
    """Before interviews: agreement, fidelity, first choices, true against observed, first-choice demand."""
    return pre_interview_page(request, RunPages(get_run(request, pk, number)))


def pre_interview_page(request: HttpRequest, pages: RunPages) -> HttpResponse:
    """Render the views before interviews of a user's run, or of a saved example."""
    run = pages.run
    pages.finished()
    metrics = run.metrics or {}
    applicants, programs = metrics.get("applicants") or {}, metrics.get("programs") or {}
    stats = [
        (
            "Applicant agreement",
            _number((applicants.get("consensus") or {}).get("true_utility_correlation"), 3),
            "how alike applicants' true preferences are",
        ),
        (
            "Program agreement",
            _number((programs.get("consensus") or {}).get("true_utility_correlation"), 3),
            "how alike programs' true preferences are",
        ),
        (
            "Applicants' fidelity",
            _number((applicants.get("fidelity") or {}).get("pooled_correlation"), 3),
            "true against pre-interview view",
        ),
        (
            "Programs' fidelity",
            _number((programs.get("fidelity") or {}).get("pooled_correlation"), 3),
            "true against pre-interview view",
        ),
    ]
    context = _run_context(pages, "pre_interview", stats=stats, charts=pages.charts(TAB_CHARTS["pre_interview"]))
    return render(request, "nrmps/runs/pre_interview.html", context)


@require_GET
def run_applications(request, pk: int, number: int):
    """Applications, signals, invitations and interviews: the funnel, and every application with filters."""
    return applications_page(request, RunPages(get_run(request, pk, number)))


def applications_page(request: HttpRequest, pages: RunPages) -> HttpResponse:
    """Render the applications and interviews of a user's run, or of a saved example."""
    run = pages.run
    data, _applicants, _programs = pages.finished()
    record = data.stages
    if record is None or not (run.metrics or {}).get("outcomes"):
        raise Http404("This run stopped before applications")
    funnel = (run.metrics or {})["outcomes"]["funnel"]
    stats = [
        ("Applications", _number(funnel.get("applications_per_applicant"), 1), "per applicant"),
        ("Invitations", _number(funnel.get("invitations_per_applicant"), 1), "per applicant"),
        (
            "Interviews",
            _number(funnel.get("interviews_per_applicant"), 1),
            f"per applicant; {_number(funnel.get('interviews_per_position'), 1)} per position",
        ),
        ("No interview", intcomma(funnel.get("applicants_without_interview", 0)), "applicants"),
    ]
    context = _run_context(
        pages,
        "applications",
        stats=stats,
        charts=pages.charts(TAB_CHARTS["applications"]),
        **_application_table(request, data, record, pages.page_sizes),
    )
    return render(request, "nrmps/runs/applications.html", context)


@require_GET
def run_match(request, pk: int, number: int):
    """The match: headline numbers, which choice applicants got, who matched where, the checks and who matched."""
    return match_page(request, RunPages(get_run(request, pk, number)))


def match_page(request: HttpRequest, pages: RunPages) -> HttpResponse:
    """Render the match of a user's run, or of a saved example."""
    run = pages.run
    metrics = run.metrics or {}
    if run.status != SimulationRun.Status.SUCCEEDED or not metrics.get("outcomes"):
        raise Http404("This run has no match")
    charts = pages.charts(TAB_CHARTS["match"])
    context = _run_context(
        pages,
        "match",
        outcome_views=_outcomes(metrics),
        charts={name: chart for name, chart in charts.items() if chart},
    )
    return render(request, "nrmps/runs/match.html", context)


# Filters of the applications table: key -> label.
APPLICATION_STATUSES = {
    "": "All applications",
    "not_invited": "Not invited",
    "invited": "Invited",
    "declined": "Invited, no interview",
    "interviewed": "Interviewed",
    "ranked": "On the applicant's list",
    "matched": "Matched",
}
APPLICATION_SORTS = ("applicant", "program", "pre_rank", "applicant_rank", "program_rank")


def _name_matches(side: Any, text: str) -> np.ndarray:
    """Return, per agent of a side, whether its name contains `text` (ignoring case)."""
    names = np.array([side.name(k).casefold() for k in range(side.size)])
    found: np.ndarray = np.char.find(names, text.casefold()) >= 0
    return found


def _application_table(request: HttpRequest, data: RunData, record: StageRecord, sizes: list[int]) -> dict[str, Any]:
    """Return the filtered, sorted and paginated applications of a run (its stage `record`), with the filters."""
    applicants, programs = data.population.applicants, data.population.programs
    matched = record.match_program[record.i] == record.j
    invited = record.invite_wave > 0
    masks = {
        "not_invited": ~invited,
        "invited": invited,
        "declined": invited & ~record.accepted,
        "interviewed": record.accepted,
        "ranked": record.applicant_rank > 0,
        "matched": matched,
    }
    status = request.GET.get("status", "")
    signal = request.GET.get("signal", "")
    applicant_text = request.GET.get("applicant", "").strip()[:100]
    program_text = request.GET.get("program", "").strip()[:100]
    keep = masks.get(status, np.ones(record.i.shape[0], dtype=np.bool_))
    if signal in {"yes", "no"}:
        keep = keep & ((record.signal_tier >= 0) == (signal == "yes"))
    if applicant_text:
        keep = keep & _name_matches(applicants, applicant_text)[record.i]
    if program_text:
        keep = keep & _name_matches(programs, program_text)[record.j]
    rows = np.flatnonzero(keep)
    sort = request.GET.get("sort", "applicant")
    sort = sort if sort in APPLICATION_SORTS else "applicant"
    order = "desc" if request.GET.get("order") == "desc" else "asc"
    unranked = np.iinfo(np.int64).max  # entries not on the list sort after every rank
    applicant_rank, program_rank = record.applicant_rank.astype(np.int64), record.program_rank.astype(np.int64)
    keys = {
        "applicant": record.i.astype(np.int64),
        "program": record.j.astype(np.int64),
        "pre_rank": record.pre_rank.astype(np.int64),
        "applicant_rank": np.where(applicant_rank > 0, applicant_rank, unranked),
        "program_rank": np.where(program_rank > 0, program_rank, unranked),
    }
    values = keys[sort][rows]
    rows = rows[np.lexsort((rows, -values if order == "desc" else values))]
    context: dict[str, Any] = {
        "sort": sort,
        "order": order,
        "filters": {"status": status, "signal": signal, "applicant": applicant_text, "program": program_text},
        "statuses": APPLICATION_STATUSES,
        "filtered": bool(status or signal in {"yes", "no"} or applicant_text or program_text),
        **_paginate(request, rows, sizes),
    }
    tiers = [tier.name for tier in data.params.signals.tiers]
    table = []
    for pair in context["page_obj"].object_list.tolist():
        i, j = int(record.i[pair]), int(record.j[pair])
        tier, wave = int(record.signal_tier[pair]), int(record.invite_wave[pair])
        table.append(
            {
                "applicant": i + 1,
                "applicant_name": applicants.name(i),
                "program": j + 1,
                "program_name": programs.name(j),
                "pre_rank": int(record.pre_rank[pair]),
                "signal": tiers[tier] if 0 <= tier < len(tiers) else "",
                "wave": wave,
                "interviewed": bool(record.accepted[pair]),
                "applicant_rank": int(record.applicant_rank[pair]) or None,
                "program_rank": int(record.program_rank[pair]) or None,
                "matched": bool(matched[pair]),
            }
        )
    context["rows"] = table
    return context


@require_GET
def run_progress(request, pk: int, number: int):
    """The progress block of a queued or running run (polled), with the stages table out of band.

    Once the run has finished, the browser reloads the page, which then shows the results.
    """
    run = get_run(request, pk, number)
    if run.is_active:
        context = {"simulation": run.simulation, "run": run, "wait": run_wait(run), "stage_rows": _stage_rows(run)}
        progress = render(request, "nrmps/runs/_progress.html", context).content.decode()
        stages = render(request, "nrmps/runs/_stages.html", context | {"oob": True}).content.decode()
        return HttpResponse(progress + stages)
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
    return applicants_page(request, RunPages(get_run(request, pk, number)))


def applicants_page(request: HttpRequest, pages: RunPages) -> HttpResponse:
    """Render the applicants of a user's run, or of a saved example."""
    data, results, programs = pages.finished()
    a, p = data.population.applicants, data.population.programs
    percentile = quantiles(a.strength) * 100
    totals = data.applicant_totals()
    keys: dict[str, np.ndarray | list[Any]] = {
        "index": list(range(a.size)),
        "name": [a.name(i) for i in range(a.size)],
        "group": [a.group_names[g] for g in a.group],
        "strength": a.strength.tolist(),
        "fidelity": np.nan_to_num(results.fidelity, nan=-2.0).tolist(),
        "popularity": programs.popularity.tolist(),
    }
    if totals is not None:
        keys["applications"] = totals["applications"].tolist()
        keys["interviews"] = totals["interviews"].tolist()
        keys["match"] = np.where(totals["match_rank"] > 0, totals["match_rank"], UNRANKED).tolist()
    indices, sort, order = _order(request, keys, "index")
    context = _run_context(
        pages,
        "applicants",
        sort=sort,
        order=order,
        has_stages=totals is not None,
        **_paginate(request, indices, pages.page_sizes),
    )
    rows = []
    for i in context["page_obj"].object_list:
        row = {
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
        if totals is not None:
            matched = int(totals["match"][i])
            row |= {
                "applications": int(totals["applications"][i]),
                "interviews": int(totals["interviews"][i]),
                "list_length": int(totals["list_length"][i]),
                "match": matched + 1 if matched >= 0 else None,
                "match_name": p.name(matched) if matched >= 0 else "",
                "match_rank": int(totals["match_rank"][i]),
            }
        rows.append(row)
    context["rows"] = rows
    return render(request, "nrmps/runs/applicants_list.html", context)


@require_GET
def run_programs(request, pk: int, number: int):
    """The run's programs with their attributes, weights, capacity and pre-interview results."""
    return programs_page(request, RunPages(get_run(request, pk, number)))


def programs_page(request: HttpRequest, pages: RunPages) -> HttpResponse:
    """Render the programs of a user's run, or of a saved example."""
    data, applicants, results = pages.finished()
    a, p = data.population.applicants, data.population.programs
    percentile = quantiles(p.quality) * 100
    totals = data.program_totals()
    keys: dict[str, np.ndarray | list[Any]] = {
        "index": list(range(p.size)),
        "name": [p.name(j) for j in range(p.size)],
        "tier": [p.tier_names[t] for t in p.tier],
        "quality": p.quality.tolist(),
        "capacity": p.capacity.tolist(),
        "fidelity": np.nan_to_num(results.fidelity, nan=-2.0).tolist(),
        "popularity": applicants.popularity.tolist(),
    }
    if totals is not None:
        keys["applications"] = totals["applications"].tolist()
        keys["interviews"] = totals["interviews"].tolist()
        keys["fill"] = (totals["filled"] / np.maximum(p.capacity, 1)).tolist()
    indices, sort, order = _order(request, keys, "index")
    context = _run_context(
        pages,
        "programs",
        sort=sort,
        order=order,
        has_stages=totals is not None,
        **_paginate(request, indices, pages.page_sizes),
    )
    rows = []
    for j in context["page_obj"].object_list:
        row = {
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
        if totals is not None:
            row |= {
                "applications": int(totals["applications"][j]),
                "interviews": int(totals["interviews"][j]),
                "list_length": int(totals["list_length"][j]),
                "filled": int(totals["filled"][j]),
            }
        rows.append(row)
    context["rows"] = rows
    return render(request, "nrmps/runs/programs_list.html", context)


def _journey(stages: StageRows) -> dict[str, Any]:
    """Return one agent's totals over the stages, for the summary above its table."""
    return {
        "applied": int(stages.applied.sum()),
        "signals": int((stages.signal >= 0).sum()),
        "invited": int((stages.wave > 0).sum()),
        "interviewed": int(stages.interviewed.sum()),
        "declined": int(((stages.wave > 0) & ~stages.interviewed).sum()),
        "ranked": int((stages.list_rank > 0).sum()),
    }


def _stage_table(
    request: HttpRequest, data: RunData, rows: PairRows, stages: StageRows, names: list[str], sizes: list[int]
) -> dict[str, Any]:
    """Return the sorted, paginated stage table of one agent: every target it applied to (or that applied to it)."""
    targets = np.flatnonzero(stages.applied)
    pre_rank = rows.observed_rank[targets]
    keys: dict[str, np.ndarray | list[Any]] = {
        "list_rank": np.where(stages.list_rank[targets] > 0, stages.list_rank[targets], UNRANKED + pre_rank).tolist(),
        "their_list_rank": np.where(
            stages.other_list_rank[targets] > 0, stages.other_list_rank[targets], UNRANKED + pre_rank
        ).tolist(),
        "pre_rank": pre_rank.tolist(),
        "name": [names[t] for t in targets],
        "index": targets.tolist(),
    }
    positions, sort, order = _order(request, keys, "list_rank")
    context = {"sort": sort, "order": order, **_paginate(request, positions, sizes)}
    tiers = [tier.name for tier in data.params.signals.tiers]
    table = []
    for position in context["page_obj"].object_list:
        t = int(targets[position])
        tier = int(stages.signal[t])
        table.append(
            {
                "number": t + 1,
                "name": names[t],
                "pre_rank": int(rows.observed_rank[t]),
                "signal": tiers[tier] if 0 <= tier < len(tiers) else "",
                "wave": int(stages.wave[t]),
                "interviewed": bool(stages.interviewed[t]),
                "post": None if np.isnan(stages.post[t]) else float(stages.post[t]),
                "their_post": None if np.isnan(stages.other_post[t]) else float(stages.other_post[t]),
                "list_rank": int(stages.list_rank[t]) or None,
                "their_list_rank": int(stages.other_list_rank[t]) or None,
                "matched": bool(stages.matched[t]),
            }
        )
    context["rows"] = table
    return context


def _pre_table(request: HttpRequest, rows: PairRows, names: list[str], sizes: list[int]) -> dict[str, Any]:
    """Return the sorted, paginated pre-interview table of one agent: every target, both sides' views."""
    keys: dict[str, np.ndarray | list[Any]] = {
        "pre_rank": rows.observed_rank.tolist(),
        "true_rank": rows.true_rank.tolist(),
        "name": names,
        "index": list(range(len(names))),
    }
    if rows.other_observed_rank is not None and rows.other_true_rank is not None:
        keys["their_pre_rank"] = rows.other_observed_rank.tolist()
        keys["their_true_rank"] = rows.other_true_rank.tolist()
    indices, sort, order = _order(request, keys, "pre_rank")
    context = {"sort": sort, "order": order, **_paginate(request, indices, sizes)}
    context["rows"] = [
        {
            "number": t + 1,
            "name": names[t],
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
    return context


def agent_page(request: HttpRequest, pages: RunPages, index: int, *, applicant: bool) -> HttpResponse:
    """Render one applicant's or program's page of a user's run, or of a saved example."""
    run = pages.run
    data, _applicants, _programs = pages.finished()
    population = data.population
    me_side = population.applicants if applicant else population.programs
    other_side = population.programs if applicant else population.applicants
    if not 1 <= index <= me_side.size:
        raise Http404("No such agent")
    agent = index - 1
    rows = data.applicant_rows(agent) if applicant else data.program_rows(agent)
    stages = data.stage_rows(agent, applicant=applicant)
    view = "pre" if stages is None or request.GET.get("view") == "pre" else "stages"
    names = [other_side.name(t) for t in range(other_side.size)]
    context: dict[str, Any] = {
        "simulation": run.simulation,
        "run": run,
        "pages": pages,
        "example": pages.example,
        "applicant": applicant,
        "index": index,
        "name": me_side.name(agent),
        "view": view,
        "has_stages": stages is not None,
        "has_their_ranks": rows.other_observed_rank is not None,
        "n_targets": other_side.size,
    }
    if stages is not None:
        matched = np.flatnonzero(stages.matched)
        context["journey"] = _journey(stages) | {
            "matched": [
                {
                    "number": int(t) + 1,
                    "name": names[t],
                    "list_rank": int(stages.list_rank[t]),
                    "their_list_rank": int(stages.other_list_rank[t]),
                }
                for t in matched
            ],
            "positions": None if applicant else int(population.programs.capacity[agent]),
        }
        context["ego"] = ego_network(stages, names, me_side.name(agent), applicant=applicant)
        # A program's funnel can be split by the strength fifth of its applicants (among all applicants).
        strength = None if applicant else np.asarray(population.applicants.strength, dtype=np.float64)
        context["funnel"] = agent_funnel(stages, me_side.name(agent), applicant=applicant, strength=strength)
    if view == "stages" and stages is not None:
        context |= _stage_table(request, data, rows, stages, names, pages.page_sizes)
    else:
        context |= _pre_table(request, rows, names, pages.page_sizes)
    return render(request, "nrmps/runs/agent_detail.html", context)


@require_GET
def run_applicant(request, pk: int, number: int, index: int):
    """One applicant's path through the stages, and its view of every program before interviews (view=pre)."""
    return agent_page(request, RunPages(get_run(request, pk, number)), index, applicant=True)


@require_GET
def run_program(request, pk: int, number: int, index: int):
    """One program's applicants through the stages, and its view of every applicant before interviews (view=pre)."""
    return agent_page(request, RunPages(get_run(request, pk, number)), index, applicant=False)


# --- Downloads --------------------------------------------------------------------------------------------------------


def _attachment[R: HttpResponse | StreamingHttpResponse](response: R, filename: str) -> R:
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()


# Downloads of the decisions from applications to the match: the columns and the rows.
STAGE_DOWNLOADS = {
    "applications.csv": (APPLICATION_COLUMNS, RunData.application_rows),
    "match.csv": (MATCH_COLUMNS, RunData.match_rows),
    "program_results.csv": (PROGRAM_RESULT_COLUMNS, RunData.program_result_rows),
}


@require_GET
def run_download(request, pk: int, number: int, name: str):
    """Download a run's applicants or programs (the upload format), results, pairs, metrics or parameters."""
    return download(request, RunPages(get_run(request, pk, number)), name)


def download(request: HttpRequest, pages: RunPages, name: str) -> HttpResponse | StreamingHttpResponse:
    """Return a file of a user's run, or of a saved example."""
    run = pages.run
    example = pages.example
    prefix = example.slug if example else f"{slugify(run.simulation.name) or 'simulation'}-run-{run.number}"
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
    data, _applicants, _programs = pages.finished()
    lines: Iterator[str]
    if name == "applicants.csv":
        lines = population_csv_lines(data.population.applicants)
    elif name == "programs.csv":
        lines = population_csv_lines(data.population.programs)
    elif name == "pairs.csv":
        if not pages.pairs_download:
            raise Http404("This run is too large for the pairs file")
        lines = plain_csv_lines(PAIR_COLUMNS, data.pair_rows())
    elif name in STAGE_DOWNLOADS:
        if data.stages is None:
            raise Http404("This run has no stage results")
        columns, rows = STAGE_DOWNLOADS[name]
        lines = plain_csv_lines(columns, rows(data))
    else:
        raise Http404("Unknown download")
    return _attachment(StreamingHttpResponse(lines, content_type="text/csv; charset=utf-8"), f"{prefix}-{name}")


# --- Comparing two runs -----------------------------------------------------------------------------------------------

RUN_KEY = re.compile(r"(\d{1,9})-(\d{1,9})")  # a run in the comparison's address: "<simulation>-<run number>"
COMPARE_CHOICES = 300  # the most recent runs the comparison's pickers offer
COMPARE_SIDES = (("a", "A", "viz-dot-series-1"), ("b", "B", "viz-dot-series-2"))


def run_key(run: SimulationRun) -> str:
    """Return the run's key in the comparison's address."""
    return f"{run.simulation_id}-{run.number}"


def _keyed_run(request: HttpRequest, key: str | None) -> SimulationRun | None:
    """Return the user's run a comparison key names, or None without a key (or with one that is not a key).

    Raises Http404 when the key names no run of the user's.
    """
    match = RUN_KEY.fullmatch(key or "")
    return get_run(request, int(match[1]), int(match[2])) if match else None


def _has_match(run: SimulationRun) -> bool:
    return run.status == SimulationRun.Status.SUCCEEDED and bool((run.metrics or {}).get("outcomes"))


def _run_choices(user: Any) -> list[dict[str, Any]]:
    """Return the user's runs with a match for the comparison's pickers, by simulation, the newest first."""
    runs = (
        SimulationRun.objects.filter(
            simulation__owner=user, status=SimulationRun.Status.SUCCEEDED, metrics__has_key="outcomes"
        )
        .select_related("simulation")
        .defer("metrics", "params", "fingerprints", "population_source")
        .order_by("-simulation_id", "-number")[:COMPARE_CHOICES]
    )
    groups: list[dict[str, Any]] = []
    for run in runs:
        if not groups or groups[-1]["pk"] != run.simulation_id:
            groups.append({"pk": run.simulation_id, "name": run.simulation.name, "runs": []})
        groups[-1]["runs"].append({"key": run_key(run), "number": run.number})
    return groups


def _compare_url(a: SimulationRun | None, b: SimulationRun | None) -> str:
    keys = {side: run_key(run) for side, run in (("a", a), ("b", b)) if run is not None}
    return reverse("nrmps:compare") + (f"?{urlencode(keys)}" if keys else "")


@require_GET
def compare(request):
    """Two runs side by side: what they share, key numbers with differences, charts with both, parameters that differ.

    The runs are `?a=` and `?b=`, each as "<simulation>-<run number>"; without both, the page asks for them.
    """
    a, b = (_keyed_run(request, request.GET.get(side)) for side in ("a", "b"))
    sides = [
        {"name": name, "letter": letter, "dot": dot, "run": run, "key": run_key(run) if run else ""}
        for (name, letter, dot), run in zip(COMPARE_SIDES, (a, b), strict=True)
    ]
    context: dict[str, Any] = {"a": a, "b": b, "sides": sides, "choices": _run_choices(request.user)}
    if a is not None and b is not None:
        context["swap_url"] = _compare_url(b, a)
        if a.is_active or b.is_active:
            context["waiting"] = [run for run in (a, b) if run.is_active]
            context["wait_url"] = reverse("nrmps:compare_wait") + "?" + urlencode({"a": run_key(a), "b": run_key(b)})
        elif a.pk == b.pk:
            context["same_run"] = True
        elif _has_match(a) and _has_match(b):
            data_a, data_b = RunData(a), RunData(b)
            pairs = pairing(a, b)
            context |= {
                "pairing": pairs,
                "groups": key_numbers(data_a, data_b),
                "differences": parameter_differences(a, b),
                "charts": comparison_charts(data_a, data_b),
                # Offered when the seeds differ and B's simulation still has B's parameters: then running it again
                # with A's seed repeats B on A's draws.
                "rerun": not pairs.same_seed and same_setup(b),
            }
        else:
            context["no_match"] = [run for run in (a, b) if not _has_match(run)]
    return render(request, "nrmps/compare.html", context)


@require_GET
def compare_wait(request):
    """Polled by the comparison page while one of its runs is queued or running: reload when both have finished."""
    runs = [_keyed_run(request, request.GET.get(side)) for side in ("a", "b")]
    response = HttpResponse(status=204)
    if not any(run is not None and run.is_active for run in runs):
        response["HX-Refresh"] = "true"
    return response


@require_POST
@rate_limit("run", by="user")
def compare_rerun(request):
    """Run B's simulation again with A's seed, and compare A with the new run.

    The simulation keeps A's seed afterwards. Offered by the comparison page when the seeds differ and B's simulation
    still has B's parameters; whatever its parameters are now, this runs them.
    """
    a, b = (_keyed_run(request, request.POST.get(side)) for side in ("a", "b"))
    if a is None or b is None:
        raise Http404("Two runs are needed")
    sim = b.simulation
    try:
        with transaction.atomic():  # a run that cannot start leaves the simulation's seed as it was
            sim.set_params(sim.get_params().with_seed(a.seed))
            sim.save()
            run = start_run(sim, request.user)
        run = dispatch_run(run)
    except ValidationError:
        messages.error(request, f"The saved parameters of “{sim.name}” are not valid. Open them, fix them and save.")
        return redirect(_compare_url(a, b))
    except SimulationError as exc:
        messages.error(request, str(exc))
        return redirect(_compare_url(a, b))
    if run.status == SimulationRun.Status.FAILED:
        messages.error(request, f"Run {run.number} of “{sim.name}” failed: {run.error}")
        return redirect(_compare_url(a, b))
    messages.success(request, f"Run {run.number} of “{sim.name}” uses the seed of run A ({a.seed}).")
    return redirect(_compare_url(a, run))
