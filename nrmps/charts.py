"""Payloads of the diagnostic charts on the run page (plan step 3.8; docs/review/E-visualization.md §1).

Each function returns plain JSON for one chart. The run page embeds it with `json_script`, static/js/nrmp-charts.js
draws it with ECharts, and the page also gives each chart's numbers as a table or a sentence, so nothing depends on
the drawing. The charts double as engine checks: the requested distributions lie over the realised ones, the
observed utilities scatter around the identity line, and the funnel's counts add up.

- POP-1 `requested_histogram`: strength and quality histograms with the counts the parameters ask for (a mixture of
  the groups' or tiers' normal distributions), when that side was generated.
- POP-4 `tightness`: positions per program, with the market's tightness.
- RAT-1 `perception_samples`: true against observed utility, for a sample of pairs before interviews and of
  interviews after them, both sides.
- RAT-3 `first_choice_demand`: how many applicants rank each program first before interviews, against its positions,
  with the Lorenz curve and the Gini coefficient.
- INT-1 `funnel`: applications through invitations, interviews and rank order lists to matches, with the drop-offs.
"""

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.special import ndtr

from .engine.interviews import pair_views
from .engine.persistence import StageRecord
from .params import SimulationParams
from .runs import RunData

SAMPLE = 1500  # points per series in the true-against-observed scatter plots
DEMAND_TABLE_ROWS = 10


def _round(values: NDArray[Any] | list[float], digits: int = 4) -> list[float]:
    return [round(float(value), digits) for value in values]


def _mixture_counts(edges: list[float], total: int, components: list[tuple[float, float, float]]) -> list[float] | None:
    """Return the expected count per bin of `total` draws from a mixture of normals (share, mean, sd)."""
    if not edges or total <= 0:
        return None
    bounds = np.asarray(edges, dtype=np.float64)
    cdf = np.zeros(bounds.size)
    for share, mean, sd in components:
        cdf += share * (ndtr((bounds - mean) / sd) if sd > 0 else (bounds >= mean).astype(np.float64))
    cdf[0], cdf[-1] = 0.0, 1.0  # the edge bins take the tails: every realised value lies within the edges
    return _round(np.diff(cdf) * total, 2)


def requested_histogram(
    metrics: dict[str, Any], params: SimulationParams, sources: dict[str, str], side: str
) -> dict[str, Any] | None:
    """Return POP-1 for one side ("applicants": strength, "programs": quality): the histogram and the request."""
    key = "strength" if side == "applicants" else "quality"
    histogram = (metrics.get("histograms") or {}).get(key)
    if not histogram:
        return None
    total = int(sum(histogram["counts"]))
    requested = None
    if sources.get(side) == "generated":
        if side == "applicants":
            components = [(g.share, g.strength_mean, g.strength_sd) for g in params.applicants.groups]
        else:
            tiers = params.programs.tiers or []
            sd = params.programs.quality_sd
            components = [(t.share, t.quality_mean, sd) for t in tiers] or [(1.0, 0.0, sd)]
        weight = sum(share for share, _mean, _sd in components) or 1.0
        requested = _mixture_counts(
            histogram["edges"], total, [(share / weight, mean, sd) for share, mean, sd in components]
        )
    return {"edges": histogram["edges"], "counts": histogram["counts"], "requested": requested}


def tightness(metrics: dict[str, Any]) -> dict[str, Any] | None:
    """Return POP-4: the histogram of positions per program and the market's size and tightness."""
    histogram = (metrics.get("histograms") or {}).get("capacity")
    if not histogram:
        return None
    return {"edges": histogram["edges"], "counts": histogram["counts"]}


def perception_samples(data: RunData, size: int = SAMPLE) -> dict[str, Any]:
    """Return RAT-1: (true, observed) samples per side, before interviews (all pairs) and after (interviews).

    The sample is drawn from the run's seed with a generator of its own, so a page always shows the same points.
    """
    rng = np.random.default_rng([data.run.seed, 31])
    model, population = data.model, data.population
    n, m = population.n_applicants, population.n_programs
    count = min(size, n * m)
    flat = rng.choice(n * m, size=count, replace=False) if n * m > count else np.arange(n * m)
    i, j = (flat // m).astype(np.int64), (flat % m).astype(np.int64)
    u = model.applicants.pair_utilities(i, j)
    v = model.programs.pair_utilities(j, i)
    result: dict[str, Any] = {
        "applicants": {"pre": [_round(u, 3), _round(u + model.applicant_view.pair_error(i, j), 3)], "post": None},
        "programs": {"pre": [_round(v, 3), _round(v + model.program_view.pair_error(j, i), 3)], "post": None},
    }
    record = data.stages
    if record is not None:
        held = np.flatnonzero(record.accepted)
        if held.size > size:
            held = np.sort(rng.choice(held, size=size, replace=False))
        if held.size:
            hi, hj = record.i[held].astype(np.int64), record.j[held].astype(np.int64)
            _u, u_star, u_post, _v, v_star, v_post = pair_views(
                data.params, model, hi, hj, data.run.seed, data.run.replicate
            )
            result["applicants"]["post"] = [_round(u_star, 3), _round(u_post, 3)]
            result["programs"]["post"] = [_round(v_star, 3), _round(v_post, 3)]
    return result


def gini(values: NDArray[Any]) -> float | None:
    """Return the Gini coefficient of non-negative values (0 = equal, 1 = all in one)."""
    x = np.sort(np.asarray(values, dtype=np.float64))
    total = x.sum()
    if x.size == 0 or total <= 0:
        return None
    n = x.size
    return float((2.0 * np.sum(np.arange(1, n + 1) * x) / (n * total)) - (n + 1) / n)


def first_choice_demand(data: RunData) -> dict[str, Any] | None:
    """Return RAT-3: first-choice demand per program (most wanted first) with its positions, the Lorenz curve and Gini.

    Demand is the number of applicants whose pre-interview first choice the program is.
    """
    if data.applicant_results is None:
        return None
    programs = data.population.programs
    demand = data.applicant_results.popularity.astype(np.int64)
    order = np.lexsort((np.arange(demand.size), -demand))
    ascending = np.sort(demand)
    total = int(demand.sum())
    lorenz = np.concatenate([[0.0], np.cumsum(ascending) / total]) if total else np.zeros(demand.size + 1)
    step = max(1, demand.size // 200)  # at most about 200 points on the curve
    points = np.unique(np.concatenate([np.arange(0, demand.size + 1, step), [demand.size]]))
    return {
        "names": [programs.name(int(j)) for j in order],
        "demand": demand[order].tolist(),
        "positions": programs.capacity[order].astype(np.int64).tolist(),
        "lorenz": [[round(float(p) / demand.size, 4), round(float(lorenz[p]), 4)] for p in points],
        "gini": gini(demand),
        "programs_wanted": int(np.count_nonzero(demand)),
        "top_share": round(float(demand[order][: max(1, demand.size // 10)].sum()) / total, 4) if total else None,
    }


def funnel(record: StageRecord | None) -> dict[str, Any] | None:
    """Return INT-1: applications through invitations, interviews and rank order lists to matches, with drop-offs."""
    if record is None:
        return None
    applied = int(record.i.shape[0])
    invited = int(np.count_nonzero(record.invite_wave > 0))
    interviewed = int(np.count_nonzero(record.accepted))
    ranked = int(np.count_nonzero(record.applicant_rank > 0))
    matched = int(np.count_nonzero(record.match_program[record.i] == record.j))
    return {
        "applied": applied,
        "invited": invited,
        "not_invited": applied - invited,
        "interviewed": interviewed,
        "declined": invited - interviewed,
        "ranked": ranked,
        "not_ranked": interviewed - ranked,
        "matched": matched,
        "not_matched": ranked - matched,
    }


def fit_check(payload: dict[str, Any]) -> float | None:
    """Return the largest deviation of the realised from the requested counts, in standard errors.

    Over bins expecting at least 5 values, |realised - requested| / sqrt(requested); above 4 the generator did not
    produce what was asked (by chance that happens in about 1 run in 1,000).
    """
    requested = payload.get("requested")
    if not requested:
        return None
    expected = np.asarray(requested, dtype=np.float64)
    realised = np.asarray(payload["counts"], dtype=np.float64)
    usable = expected >= 5
    if not usable.any():
        return None
    return round(float(np.max(np.abs(realised[usable] - expected[usable]) / np.sqrt(expected[usable]))), 2)


def digits(edges: list[float]) -> int:
    """Return the decimals that tell the bin edges apart: one more than the bin width needs."""
    width = (edges[-1] - edges[0]) / max(1, len(edges) - 1)
    return 0 if width <= 0 else max(0, math.ceil(-math.log10(width)) + 1)


def _histogram_chart(payload: dict[str, Any] | None, what: str, unit: str) -> dict[str, Any] | None:
    """Return a histogram chart: the payload, a summary sentence and the rows of its data table."""
    if payload is None:
        return None
    edges, counts = payload["edges"], payload["counts"]
    requested = payload.get("requested") or [None] * len(counts)
    total = sum(counts)
    places = digits(edges)
    summary = (
        f"{what}: {total:,} {unit} in {len(counts)} bins from {edges[0]:.{places}f} to {edges[-1]:.{places}f}; the "
        f"fullest bin holds {max(counts):,}."
    )
    deviation = fit_check(payload)
    if deviation is not None:
        summary += (
            f" The line shows the counts the parameters ask for; the largest deviation is {deviation:.1f} standard "
            f"errors{' (more than 4: check the generator)' if deviation > 4 else ''}."
        )
    rows = [
        {"low": low, "high": high, "count": count, "requested": wanted}
        for low, high, count, wanted in zip(edges[:-1], edges[1:], counts, requested, strict=True)
    ]
    return {"payload": payload, "summary": summary, "rows": rows, "deviation": deviation, "digits": places}


def _correlation(pair: list[list[float]] | None) -> float | None:
    if not pair or len(pair[0]) < 3:
        return None
    x, y = np.asarray(pair[0]), np.asarray(pair[1])
    if x.std() == 0 or y.std() == 0:
        return None
    return round(float(np.corrcoef(x, y)[0, 1]), 3)


def _perception_chart(payload: dict[str, Any], side: str) -> dict[str, Any]:
    pre, post = payload["pre"], payload["post"]
    who = "applicants' views of programs" if side == "applicants" else "programs' views of applicants"
    summary = (
        f"True against observed utility, {who}: {len(pre[0]):,} sampled pairs before interviews (correlation "
        f"{_correlation(pre)})"
    )
    summary += (
        f" and {len(post[0]):,} sampled interviews after them, realised utility against the post-interview view "
        f"(correlation {_correlation(post)})."
        if post
        else "."
    )
    return {"payload": payload, "summary": summary}


# The charts of each run page tab.
TAB_CHARTS = {
    "population": ("strength", "quality", "capacity"),
    "pre_interview": ("applicant_fidelity", "program_fidelity", "perception", "demand"),
    "applications": ("funnel",),
}


def _demand_charts(data: RunData) -> dict[str, Any]:
    demand = first_choice_demand(data)
    if demand is None:
        return {}
    wanted, total = demand["programs_wanted"], len(demand["demand"])
    top = demand["top_share"]
    gini_text = "-" if demand["gini"] is None else f"{demand['gini']:.3f}"
    return {
        "demand": {
            "payload": demand,
            "summary": (
                f"First-choice demand: {wanted:,} of {total:,} programs are some applicant's first choice before "
                f"interviews; the most wanted tenth of programs gets {'-' if top is None else f'{top * 100:.1f}%'} of "
                f"first choices (Gini {gini_text})."
            ),
            "rows": [
                {"name": name, "demand": count, "positions": positions}
                for name, count, positions in zip(
                    demand["names"][:DEMAND_TABLE_ROWS],
                    demand["demand"][:DEMAND_TABLE_ROWS],
                    demand["positions"][:DEMAND_TABLE_ROWS],
                    strict=True,
                )
            ],
        },
        "lorenz": {
            "payload": None,
            "summary": (
                "The Lorenz curve of first-choice demand: programs from the least to the most wanted against their "
                "cumulative share of first choices; the dashed diagonal is equal demand, and the Gini coefficient "
                f"({gini_text}) is twice the area between them."
            ),
        },
    }


def _funnel_chart(record: StageRecord | None) -> dict[str, Any]:
    counts = funnel(record)
    if counts is None:
        return {}
    applied = counts["applied"] or 1
    return {
        "funnel": {
            "payload": counts,
            "summary": (
                f"Of {counts['applied']:,} applications, {counts['invited']:,} led to an interview invitation, "
                f"{counts['interviewed']:,} to an interview, {counts['ranked']:,} to a place on the applicant's "
                f"rank order list and {counts['matched']:,} to a match."
            ),
            "rows": [
                {"stage": label, "count": counts[key], "share": counts[key] / applied}
                for key, label in (
                    ("applied", "Applied"),
                    ("invited", "Invited"),
                    ("interviewed", "Interviewed"),
                    ("ranked", "On the applicant's list"),
                    ("matched", "Matched"),
                )
            ],
        }
    }


def run_charts(data: RunData, names: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Return the charts `names` (default: all) of a finished run: payload, summary sentence and table rows.

    A chart the run has no data for is None or missing. "perception" gives perception_applicants and
    perception_programs; "demand" gives demand and lorenz.
    """
    wanted = set(names) if names is not None else {name for tab in TAB_CHARTS.values() for name in tab}
    run = data.run
    metrics = run.metrics or {}
    histograms = metrics.get("histograms") or {}
    sources = {
        side: "generated" if label == "generated" else "uploaded" for side, label in run.population_source.items()
    }
    charts: dict[str, Any] = {}
    if "strength" in wanted:
        payload = requested_histogram(metrics, data.params, sources, "applicants")
        charts["strength"] = _histogram_chart(payload, "Applicant strength", "applicants")
    if "quality" in wanted:
        payload = requested_histogram(metrics, data.params, sources, "programs")
        charts["quality"] = _histogram_chart(payload, "Program quality", "programs")
    if "capacity" in wanted:
        charts["capacity"] = _histogram_chart(tightness(metrics), "Positions per program", "programs")
    if "applicant_fidelity" in wanted:
        charts["applicant_fidelity"] = _histogram_chart(
            histograms.get("applicant_fidelity"), "Applicants' pre-interview fidelity", "applicants"
        )
    if "program_fidelity" in wanted:
        charts["program_fidelity"] = _histogram_chart(
            histograms.get("program_fidelity"), "Programs' pre-interview fidelity", "programs"
        )
    if "perception" in wanted:
        perception = perception_samples(data)
        charts["perception_applicants"] = _perception_chart(perception["applicants"], "applicants")
        charts["perception_programs"] = _perception_chart(perception["programs"], "programs")
    if "demand" in wanted:
        charts |= _demand_charts(data)
    if "funnel" in wanted:
        charts |= _funnel_chart(data.stages)
    return charts
