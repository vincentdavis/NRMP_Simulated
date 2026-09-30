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
- `applicant_flow`: every applicant counted once, from applying to an interview and a match, optionally split into
  fifths of applicant strength (the "Colour by strength" switch), so the quality of the applicants can be followed
  through the stages.
- MAT-7 (ego) `ego_network`: one applicant's or program's applications by how far each got, drawn as a network with
  sigma.js on the agent's page (plan step 5.1), next to `agent_funnel`, the same funnel for that agent alone.
"""

import math
from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.special import ndtr

from .engine.interviews import pair_views
from .engine.persistence import StageRecord
from .params import SimulationParams
from .runs import RunData, StageRows

SAMPLE = 1500  # points per series in the true-against-observed scatter plots
DEMAND_TABLE_ROWS = 10
EGO_MAX_NODES = 2000  # an agent's network draws at most this many applications, those that got furthest first
# The applicants' flow: its stages, the drop-off after each (and who it holds), and the strength fifths, named by
# percentile and coloured by the diverging scale (--viz-div-1 to 5: red below the middle, grey, blue above it).
FLOW_STAGES = ("Applicants", "Interviewed", "Matched")
FLOW_DROPS = ("No interview", "Interviewed, not matched")
FLOW_DROP_WHO = {"No interview": "with no interview", "Interviewed, not matched": "interviewed but not matched"}
STRENGTH_BANDS = (
    "Bottom 20%",
    "20th\u201340th percentile",
    "40th\u201360th percentile",
    "60th\u201380th percentile",
    "Top 20%",
)
STRENGTH_RANGES = ("0\u201320", "20\u201340", "40\u201360", "60\u201380", "80\u2013100")
# How far an application got, in order; each is exclusive (an interview that led nowhere is "Interviewed").
EGO_STAGES = ("Applied", "Invited", "Interviewed", "Ranked", "Matched")
EGO_KEY = (
    ("Not invited", "viz-dot-neutral"),
    ("Invited, no interview", "viz-dot-seq-2"),
    ("Interviewed, not ranked", "viz-dot-seq-3"),
    ("Ranked, not matched", "viz-dot-seq-4"),
    ("Matched", "viz-dot-series-3"),
)


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


def funnel_counts(applied: int, invited: int, interviewed: int, ranked: int, matched: int) -> dict[str, int]:
    """Return a funnel's stages and the drop-off between each and the next (each stage holds the next one)."""
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


def funnel(record: StageRecord | None) -> dict[str, Any] | None:
    """Return INT-1: applications through invitations, interviews and rank order lists to matches, with drop-offs."""
    if record is None:
        return None
    return funnel_counts(
        int(record.i.shape[0]),
        int(np.count_nonzero(record.invite_wave > 0)),
        int(np.count_nonzero(record.accepted)),
        int(np.count_nonzero(record.applicant_rank > 0)),
        int(np.count_nonzero(record.match_program[record.i] == record.j)),
    )


FUNNEL_ROWS = ("applied", "invited", "interviewed", "ranked", "matched")  # the funnel's stages, in its table


def funnel_chart(counts: dict[str, int], *, of: str, whose: str) -> dict[str, Any]:
    """Return a funnel chart: the payload, a summary sentence and the rows of its table.

    `of` names the applications ("474 applications"); `whose` is whose rank order list "Ranked" means
    ("applicant's" or "program's").
    """
    applied = counts["applied"] or 1
    labels = ("Applied", "Invited", "Interviewed", f"On the {whose} list", "Matched")
    return {
        "payload": counts,
        "summary": (
            f"Of {of}, {counts['invited']:,} led to an interview invitation, {counts['interviewed']:,} to an "
            f"interview, {counts['ranked']:,} to a place on the {whose} rank order list and {counts['matched']:,} to "
            "a match."
        ),
        "rows": [
            {"stage": label, "count": counts[key], "share": counts[key] / applied}
            for key, label in zip(FUNNEL_ROWS, labels, strict=True)
        ],
    }


def agent_funnel(
    stages: StageRows, name: str, *, applicant: bool, strength: NDArray[np.float64] | None = None
) -> dict[str, Any] | None:
    """Return INT-1 for one applicant or program: its applications through the stages, or None without any.

    "Ranked" is the agent's own rank order list: the applicant's on an applicant's page, the program's on a program's
    (an applicant it ranked may still have matched elsewhere). On a program's page, `strength` (every applicant's)
    splits the applications by the applicant's strength fifth among all applicants, for the Colour by strength switch
    (payload "bands", as in the applicants' flow), the table and the summary.
    """
    applied = stages.applied
    if not applied.any():
        return None

    def counts_of(mask: NDArray[np.bool_]) -> dict[str, int]:
        return funnel_counts(
            int(mask.sum()),
            int((mask & (stages.wave > 0)).sum()),
            int((mask & stages.interviewed).sum()),
            int((mask & (stages.list_rank > 0)).sum()),
            int((mask & stages.matched).sum()),
        )

    counts = counts_of(applied)
    total = f"{counts['applied']:,}"
    if applicant:
        return funnel_chart(counts, of=f"{name}'s {total} applications", whose="applicant's")
    chart = funnel_chart(counts, of=f"the {total} applications to {name}", whose="program's")
    if strength is None:
        return chart
    bands = strength_bands(strength)
    groups = None if bands is None else _strength_groups(strength, bands, lambda fifth: counts_of(applied & fifth))
    chart |= {
        "payload": counts | {"bands": groups},
        "switchable": groups is not None,
        "switch_note": _strength_note(strength.size, groups is not None),
        "switch_key": None if groups is None else strength_key(),
    }
    if groups is not None:
        chart["band_ranges"] = STRENGTH_RANGES
        for row, key in zip(chart["rows"], FUNNEL_ROWS, strict=True):
            row["bands"] = [group["counts"][key] for group in groups]
        top = groups[-1]["counts"]
        held = [
            f"{_share(top[key], counts[key])} of the {what}"
            for key, what in (("interviewed", "interviews"), ("matched", "matches"))
            if counts[key]
        ]
        chart["summary"] += (
            f" The {STRENGTH_BANDS[-1].lower()} of applicants by strength sent "
            f"{_share(top['applied'], counts['applied'])} of these applications"
            + (f" and had {' and '.join(held)}." if held else ".")
        )
    return chart


def strength_bands(strength: NDArray[np.float64]) -> NDArray[np.int64] | None:
    """Return each applicant's strength fifth (0 = the weakest fifth ... 4 = the strongest), or None.

    Fifths are by rank, each rank taken at its centre (rank + 1/2), so the applicants left over when n is not a
    multiple of five are spread across the fifths rather than given to the weakest. Applicants with the same strength
    stay together, in the fifth their middle rank falls in, so a tie at the top is treated like one at the bottom
    (except a tie whose middle falls exactly on the border of two fifths). None when there are fewer than five
    applicants, or when ties
    (an upload with a few distinct values) would leave a "fifth" with under 10% or over 30% of the applicants (beyond
    the rounding of n / 5): such bands would not be fifths.
    """
    n = strength.size
    k = len(STRENGTH_BANDS)
    if n < k:
        return None
    order = np.sort(strength)
    first = np.searchsorted(order, strength, side="left")  # the lowest rank of the applicant's tie group
    last = np.searchsorted(order, strength, side="right") - 1  # and its highest
    bands = ((first + last + 1) * k) // (2 * n)  # the fifth of the middle rank's centre, (first + last + 1) / 2
    sizes = np.bincount(bands, minlength=k)
    if sizes.max() > max(-(-n // k), 0.3 * n) or sizes.min() < min(n // k, 0.1 * n):
        return None
    return bands.astype(np.int64)


Mask = NDArray[np.bool_]


def _flow_counts(interviewed: Mask, matched: Mask, invited: Mask) -> dict[str, int]:
    applicants = int(interviewed.size)
    got_interview = int(interviewed.sum())
    return {
        "Applicants": applicants,
        "Interviewed": got_interview,
        "Matched": int((interviewed & matched).sum()),
        "No interview": applicants - got_interview,
        "Interviewed, not matched": int((interviewed & ~matched).sum()),
        # Not drawn: the two kinds of "No interview", for the table and the tooltips.
        "never_invited": int((~invited).sum()),
        "invited_no_interview": int((invited & ~interviewed).sum()),
    }


def applicant_flow(data: RunData) -> dict[str, Any] | None:
    """Return the applicants' flow: each applicant once, from applying to an interview and a match.

    The counts are given in total and per strength fifth (None for runs from before the match). An applicant counts
    as interviewed with at least one interview; one can be invited and still have none (every program that invited
    them filled its slots first). A match needs an interview, so the flow adds up.
    """
    record = data.stages
    if record is None:
        return None
    population = data.population
    n = population.n_applicants
    invited = np.bincount(record.i[record.invite_wave > 0], minlength=n) > 0
    interviewed = np.bincount(record.i[record.accepted.astype(bool)], minlength=n) > 0
    matched = np.asarray(record.match_program) >= 0
    strength = np.asarray(population.applicants.strength, dtype=np.float64)
    bands = strength_bands(strength)
    counts = _flow_counts(interviewed, matched, invited)
    payload: dict[str, Any] = {
        "stages": list(FLOW_STAGES),
        "drops": list(FLOW_DROPS),
        "counts": counts,
        "bands": None,
        # The two kinds of "No interview", shown in its tooltip.
        "notes": {
            "No interview": [
                ["Never invited", counts["never_invited"]],
                ["Invited, no interview", counts["invited_no_interview"]],
            ]
        },
    }
    if bands is not None:
        payload["bands"] = _strength_groups(
            strength, bands, lambda fifth: _flow_counts(interviewed[fifth], matched[fifth], invited[fifth])
        )
    return payload


def _strength_groups(
    strength: NDArray[np.float64], bands: NDArray[np.int64], counts_of: Callable[[NDArray[np.bool_]], dict[str, int]]
) -> list[dict[str, Any]]:
    """Return each strength fifth's label, strength range (over all its applicants) and counts.

    `counts_of` gets the fifth as a mask over all applicants.
    """
    return [
        {
            "label": label,
            "low": round(float(strength[bands == b].min()), 2),
            "high": round(float(strength[bands == b].max()), 2),
            "counts": counts_of(bands == b),
        }
        for b, label in enumerate(STRENGTH_BANDS)
    ]


def strength_key() -> dict[str, Any]:
    """Return the key of the Colour by strength switch: the scale from the bottom 20% to the top 20%."""
    return {
        "caption": "Strength percentile",
        "low": "weaker",
        "high": "stronger",
        "steps": [
            {"label": label, "range": STRENGTH_RANGES[b], "dot": f"viz-dot-div-{b + 1}"}
            for b, label in enumerate(STRENGTH_BANDS)
        ],
    }


def _strength_note(applicants: int, split: bool) -> str:
    """Say why the applicants cannot be split into strength fifths ("" when they can)."""
    if split:
        return ""
    if applicants < len(STRENGTH_BANDS):
        return f"fewer than {len(STRENGTH_BANDS)} applicants"
    return "too many applicants share a strength to split them into fifths"


def _bands_note(payload: dict[str, Any]) -> str:
    """Say why the flow cannot be split into strength fifths ("" when it can)."""
    return _strength_note(payload["counts"]["Applicants"], bool(payload["bands"]))


def _share(part: int, whole: int) -> str:
    return "-" if whole == 0 else f"{100 * part / whole:.1f}%"


def _applicant_flow_chart(data: RunData) -> dict[str, Any] | None:
    payload = applicant_flow(data)
    if payload is None:
        return None
    counts = payload["counts"]
    summary = (
        f"Of {counts['Applicants']:,} applicants, {counts['Interviewed']:,} had at least one interview and "
        f"{counts['Matched']:,} matched ({_share(counts['Matched'], counts['Applicants'])}); "
        f"{counts['No interview']:,} had no interview, {counts['never_invited']:,} of them never invited."
    )
    groups = [("All applicants", None, None, counts)]
    if payload["bands"]:
        weakest, strongest = payload["bands"][0]["counts"], payload["bands"][-1]["counts"]
        bottom, top = STRENGTH_BANDS[0].lower(), STRENGTH_BANDS[-1].lower()
        summary += (
            f" By strength, {_share(weakest['Matched'], weakest['Applicants'])} of the {bottom} matched, "
            f"against {_share(strongest['Matched'], strongest['Applicants'])} of the {top}."
        )
        held = [
            f"{weakest[drop]:,} of the {counts[drop]:,} {FLOW_DROP_WHO[drop]}" for drop in FLOW_DROPS if counts[drop]
        ]
        if held:
            summary += f" The {bottom} make up {' and '.join(held)}."
        groups = [(band["label"], band["low"], band["high"], band["counts"]) for band in payload["bands"]] + groups
    rows = [
        {
            "label": label,
            "low": low,
            "high": high,
            "applicants": group["Applicants"],
            "never_invited": group["never_invited"],
            "invited_no_interview": group["invited_no_interview"],
            "interviewed": group["Interviewed"],
            "not_matched": group["Interviewed, not matched"],
            "matched": group["Matched"],
            "match_share": group["Matched"] / group["Applicants"] if group["Applicants"] else None,
        }
        for label, low, high, group in groups
    ]
    return {
        "payload": payload,
        "summary": summary,
        "rows": rows,
        "switchable": bool(payload["bands"]),
        "switch_note": _bands_note(payload),
        "switch_key": strength_key() if payload["bands"] else None,
    }


def ego_network(stages: StageRows, names: list[str], name: str, *, applicant: bool) -> dict[str, Any] | None:
    """Return MAT-7 for one agent: its applications by how far each got, with a summary and the key's counts.

    Stages, from `stages` (the agent's view): 0 applied but not invited, 1 invited without an interview, 2 interviewed
    but not on the agent's rank order list, 3 on the list but not matched, 4 matched. None without applications.
    """
    targets = np.flatnonzero(stages.applied)
    if targets.size == 0:
        return None
    stage = np.zeros(targets.size, dtype=np.int64)
    stage[stages.wave[targets] > 0] = 1
    stage[stages.interviewed[targets]] = 2
    stage[stages.list_rank[targets] > 0] = 3
    stage[stages.matched[targets]] = 4
    counts = np.bincount(stage, minlength=len(EGO_STAGES))
    shown = np.lexsort((targets, -stage))[:EGO_MAX_NODES]  # the furthest first
    total = int(targets.size)
    furthest_first = zip(reversed(EGO_KEY), reversed(counts.tolist()), strict=True)
    parts = "; ".join(f"{count:,} {label.lower()}" for (label, _dot), count in furthest_first)
    who = f"{name}'s {total:,} applications" if applicant else f"The {total:,} applications to {name}"
    summary = f"{who} by how far each got: {parts}."
    if total > EGO_MAX_NODES:
        summary += f" The network shows the {EGO_MAX_NODES:,} that got furthest."
    return {
        "payload": {
            "center": name,
            "side": "applicant" if applicant else "program",
            "stages": list(EGO_STAGES),
            "nodes": [[names[int(targets[k])], int(stage[k])] for k in shown],
        },
        "summary": summary,
        "legend": [
            {"label": "This applicant", "dot": "viz-dot-series-1"}
            if applicant
            else {"label": "This program", "dot": "viz-dot-series-2"},
            *(
                {"label": label, "dot": dot, "count": count}
                for (label, dot), count in zip(EGO_KEY, counts.tolist(), strict=True)
            ),
        ],
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
    "applications": ("funnel", "applicant_flow"),
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
    return {"funnel": funnel_chart(counts, of=f"{counts['applied']:,} applications", whose="applicant's")}


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
    if "applicant_flow" in wanted:
        charts["applicant_flow"] = _applicant_flow_chart(data)
    return charts
