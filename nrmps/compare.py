"""Two runs side by side (the comparison page): what they share, what differs, and charts with both.

Its parts are the runs' key numbers with their differences, the parameters that differ, and charts that put both runs
on one question. The runs are called A and B, and differences are B minus A. `pairing` says how far the two can be
compared. A run is
a function of its parameters and its seed alone, and every random draw comes from its own stream (model_spec.md
§12), so two runs with the same seed are the same up to the first stage that a differing parameter reaches; their
stage fingerprints say which. Everything here is computed from the stored runs when the page is shown.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .charts import (
    STRENGTH_BANDS,
    applicant_flow,
    interviews_per_applicant,
    match_by_strength,
    matched_choice,
    program_fill,
    run_charts,
    sorting,
)
from .help_registry import param_value
from .models import IMPLEMENTED_STAGES, SimulationRun
from .params import SimulationParams, iter_fields, list_fields
from .runs import RunData

# --- What the runs share --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pairing:
    """How far two runs can be compared: what they share, and the stage from which they differ."""

    same_seed: bool
    same_population: bool  # the same applicants and programs (the stored populations are identical)
    shared: tuple[str, ...]  # the labels of the stages both runs computed identically, in order
    differs_from: str  # the label of the first stage that differs ("" when the runs are identical)

    @property
    def identical(self) -> bool:
        """Whether both runs have the same parameters and seed, so the same results."""
        return not self.differs_from

    @property
    def paired(self) -> bool:
        """Whether a difference between the runs comes from their parameters rather than from different draws."""
        return bool(self.shared)

    @property
    def note(self) -> str:
        """Say, for the reader, what the runs share and what that means for the differences."""
        if self.identical:
            return "These two runs have the same parameters and the same seed, so their results are the same."
        if self.shared:
            return (
                "Both runs have the same seed and the same applicants and programs. They are the same up to the "
                f"{self.shared[-1]} stage and first differ at the {self.differs_from} stage, so the differences "
                "below come from the parameters that differ. Another seed would give somewhat different numbers."
            )
        if self.same_population:
            return (
                "Both runs have the same applicants and programs, but the random steps after the population were "
                "drawn differently, so a difference of a point or two between the runs can be chance."
            )
        if self.same_seed:
            return (
                "The runs have the same seed, but the parameters that build the population differ, so their "
                "applicants and programs differ too."
            )
        return (
            "The runs have different seeds, so different applicants and programs: a difference of a point or two "
            "between them can be chance alone. For a fair comparison, give both the same seed."
        )


def pairing(a: SimulationRun, b: SimulationRun) -> Pairing:
    """Return what runs `a` and `b` share, from their seeds, stored populations and stage fingerprints."""
    shared: list[str] = []
    differs_from = ""
    for stage in IMPLEMENTED_STAGES:
        mine, theirs = a.fingerprints.get(stage.value), b.fingerprints.get(stage.value)
        if not mine or mine != theirs:
            differs_from = str(stage.label)
            break
        shared.append(str(stage.label))
    return Pairing(
        same_seed=a.seed == b.seed,
        same_population=bool(a.population_digest) and a.population_digest == b.population_digest,
        shared=tuple(shared),
        differs_from=differs_from,
    )


def same_setup(run: SimulationRun) -> bool:
    """Return whether the run's simulation still has the run's parameters, apart from the seed.

    Then running the simulation again with another seed repeats this run with that seed.
    """
    try:
        draft = run.simulation.get_params()
    except ValidationError:
        return False
    return draft.with_seed(None).params_hash() == run.get_params().with_seed(None).params_hash()


# --- Key numbers ----------------------------------------------------------------------------------------------------

# How each kind of number is shown, and its difference: a count, a share (the difference in percentage points), and
# numbers with one or three decimals.
_SHOWN = {
    "count": lambda value: f"{round(value):,}",
    "share": lambda value: f"{value * 100:.1f}%",
    "one": lambda value: f"{value:.1f}",
    "three": lambda value: f"{value:.3f}",
}
_DIFFERENCE = {
    "count": lambda value: f"{round(value):+,}",
    "share": lambda value: f"{value * 100:+.1f} pts",
    "one": lambda value: f"{value:+.1f}",
    "three": lambda value: f"{value:+.3f}",
}

# The key numbers in the page's order: (group, [(key in `_numbers`, label, kind)]).
NUMBERS: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...] = (
    (
        "The market",
        (("applicants", "Applicants", "count"), ("programs", "Programs", "count"), ("positions", "Positions", "count")),
    ),
    (
        "Before interviews",
        (
            ("applicant_agreement", "Applicant agreement", "three"),
            ("program_agreement", "Program agreement", "three"),
            ("applicant_fidelity", "Applicants' fidelity", "three"),
            ("program_fidelity", "Programs' fidelity", "three"),
        ),
    ),
    (
        "Applications and interviews",
        (
            ("applications", "Applications per applicant", "one"),
            ("interviews", "Interviews per applicant", "one"),
            ("no_interview", "Applicants with no interview", "share"),
        ),
    ),
    (
        "The match",
        (
            ("match_rate", "Match rate (applicants with a rank order list)", "share"),
            ("matched", "Applicants matched (of all applicants)", "share"),
            ("bottom_matched", f"Matched, {STRENGTH_BANDS[0].lower()} of applicants by strength", "share"),
            ("top_matched", f"Matched, {STRENGTH_BANDS[-1].lower()} of applicants by strength", "share"),
            ("filled", "Positions filled", "share"),
            ("first_choice", "Matched to their first choice", "share"),
            ("top3", "Matched to one of their top 3", "share"),
            ("sorting", "Sorting", "three"),
        ),
    ),
)


def _get(data: Any, *path: str) -> Any:
    """Return the value at `path` in nested dicts, or None where the path ends early."""
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _ratio(part: float | None, whole: float | None) -> float | None:
    return None if part is None or not whole else part / whole


def shown(value: float | None, kind: str) -> str:
    """Return a number as the page shows it ("-" when the run has none)."""
    return "-" if value is None else _SHOWN[kind](value)


def difference(a: float | None, b: float | None, kind: str) -> str:
    """Return B minus A with its sign (percentage points for shares), "-" when either run has no number.

    A difference that rounds to nothing is shown without a sign.
    """
    if a is None or b is None:
        return "-"
    text = _DIFFERENCE[kind](b - a)
    return text.lstrip("+-") if not any(character in "123456789" for character in text) else text


def _numbers(data: RunData) -> dict[str, float | None]:
    """Return one run's key numbers by key (None for a number the run does not have)."""
    run = data.run
    metrics = run.metrics or {}
    match = _get(metrics, "outcomes", "match") or {}
    funnel = _get(metrics, "outcomes", "funnel") or {}
    bands = (applicant_flow(data) or {}).get("bands")
    sorted_ = sorting(data)

    def matched_share(band: int) -> float | None:
        return _ratio(bands[band]["counts"]["Matched"], bands[band]["counts"]["Applicants"]) if bands else None

    return {
        "applicants": run.n_applicants,
        "programs": run.n_programs,
        "positions": run.n_positions,
        "applicant_agreement": _get(metrics, "applicants", "consensus", "true_utility_correlation"),
        "program_agreement": _get(metrics, "programs", "consensus", "true_utility_correlation"),
        "applicant_fidelity": _get(metrics, "applicants", "fidelity", "pooled_correlation"),
        "program_fidelity": _get(metrics, "programs", "fidelity", "pooled_correlation"),
        "applications": funnel.get("applications_per_applicant"),
        "interviews": funnel.get("interviews_per_applicant"),
        "no_interview": _ratio(funnel.get("applicants_without_interview"), run.n_applicants),
        "match_rate": match.get("match_rate"),
        "matched": _ratio(match.get("matched"), run.n_applicants),
        "bottom_matched": matched_share(0),
        "top_matched": matched_share(-1),
        "filled": match.get("fill_rate"),
        "first_choice": match.get("first_choice_share"),
        "top3": match.get("top3_share"),
        "sorting": sorted_["sorting"] if sorted_ else None,
    }


def key_numbers(a: RunData, b: RunData) -> list[dict[str, Any]]:
    """Return the two runs' key numbers in groups: each row's label, A, B and the difference B minus A, as text."""
    mine, theirs = _numbers(a), _numbers(b)
    return [
        {
            "title": title,
            "rows": [
                {
                    "label": label,
                    "a": shown(mine[key], kind),
                    "b": shown(theirs[key], kind),
                    "difference": difference(mine[key], theirs[key], kind),
                }
                for key, label, kind in rows
            ],
        }
        for title, rows in NUMBERS
    ]


# --- The parameters that differ -------------------------------------------------------------------------------------


def _list_text(items: list[dict[str, Any]], other: list[dict[str, Any]]) -> str:
    """Return a list parameter in a few words: how many rows and their names; "other values" when only values differ."""
    names = [str(item.get("name") or item.get("key") or "") for item in items]
    text = f"{len(items)}: {', '.join(names)}" if any(names) else f"{len(items)} rows"
    same_names = names == [str(item.get("name") or item.get("key") or "") for item in other]
    return f"{text} (other values)" if same_names else text


def parameter_differences(a: SimulationRun, b: SimulationRun) -> list[dict[str, str]]:
    """Return the implemented parameters whose values differ between the runs, in the order of the parameter form.

    Each row has the parameter's section and title and both values as text; the seed is one of them. A list (the
    applicant groups, say) is one row, with its rows' names.
    """
    data = [run.get_params().to_json_data() for run in (a, b)]
    sections = [name for name in SimulationParams.model_fields if name != "schema_version"]
    titles = {name: SimulationParams.model_fields[name].title or name for name in sections}
    found: list[tuple[int, int, dict[str, str]]] = []

    def add(path: str, title: str, mine: str, theirs: str) -> None:
        section = path.split(".")[0]
        row = {"section": titles[section], "title": title, "a": mine, "b": theirs}
        found.append((sections.index(section), len(found), row))

    for spec in iter_fields(SimulationParams):
        mine, theirs = (_get(side, *spec.path.split(".")) for side in data)
        if spec.implemented and mine != theirs:
            add(spec.path, spec.title, param_value(mine), param_value(theirs))
    for path, field, _item in list_fields():
        mine, theirs = (_get(side, *path.split(".")) or [] for side in data)
        if mine != theirs:
            add(path, field.title or path, _list_text(mine, theirs), _list_text(theirs, mine))
    return [row for _section, _order, row in sorted(found, key=lambda entry: entry[:2])]


# --- Charts: both runs on one question ------------------------------------------------------------------------------

Pairs = list[tuple[int, int]]  # per category: how many, of how many


def _versus(labels: list[str], names: list[str], unit: str, a: Pairs, b: Pairs, *, whole: bool) -> dict[str, Any]:
    """Return a chart of two runs on the same categories: each run's share per category, with its counts.

    `a` and `b` give, per category, a count and the total it is a share of (a share of nothing is None); `whole` says
    the shares are of each category itself (0 to 100%), not parts of one distribution.
    """

    def run_of(name: str, pairs: Pairs) -> dict[str, Any]:
        return {
            "name": name,
            "values": [_ratio(count, total) for count, total in pairs],
            "counts": [count for count, _total in pairs],
            "totals": [total for _count, total in pairs],
        }

    runs = [run_of("A", a), run_of("B", b)]
    rows = [
        {
            "label": name,
            "a": runs[0]["values"][k],
            "a_count": a[k][0],
            "a_total": a[k][1],
            "b": runs[1]["values"][k],
            "b_count": b[k][0],
            "b_total": b[k][1],
            "difference": difference(runs[0]["values"][k], runs[1]["values"][k], "share"),
        }
        for k, name in enumerate(names)
    ]
    return {"payload": {"labels": labels, "names": names, "unit": unit, "whole": whole, "runs": runs}, "rows": rows}


def _percent(value: float | None) -> str:
    return shown(value, "share")


Payload = dict[str, Any]


def _both(payload_of: Callable[[RunData], Payload | None], a: RunData, b: RunData) -> tuple[Payload, Payload] | None:
    """Return both runs' payloads of a chart, or None when either run has none."""
    mine, theirs = payload_of(a), payload_of(b)
    return None if mine is None or theirs is None else (mine, theirs)


def _strength(a: RunData, b: RunData) -> dict[str, Any] | None:
    """Who matched, by strength decile: the share of each decile's applicants who matched, in A and in B."""
    payloads = _both(match_by_strength, a, b)
    if payloads is None:
        return None

    def pairs(payload: Payload) -> Pairs:
        matched = payload["series"][0]["counts"]
        totals = [sum(parts) for parts in zip(*(series["counts"] for series in payload["series"]), strict=True)]
        return list(zip(matched, totals, strict=True))

    first = payloads[0]
    chart = _versus(first["labels"], first["names"], "applicants", pairs(first), pairs(payloads[1]), whole=True)
    mine, theirs = (run["values"] for run in chart["payload"]["runs"])
    both = [(k, x, y) for k, (x, y) in enumerate(zip(mine, theirs, strict=True)) if x is not None and y is not None]
    gaps = [(abs(y - x), k) for k, x, y in both]
    chart["summary"] = (
        f"Of the weakest tenth of applicants by strength, {_percent(mine[0])} matched in A and {_percent(theirs[0])} "
        f"in B; of the strongest tenth, {_percent(mine[-1])} and {_percent(theirs[-1])}."
    )
    if gaps and max(gaps)[0] > 0:
        k = max(gaps)[1]
        chart["summary"] += (
            f" The runs differ most in decile {k + 1}: {difference(mine[k], theirs[k], 'share')} in B "
            f"({_percent(mine[k])} against {_percent(theirs[k])})."
        )
    chart["head"] = "Strength decile"
    return chart


def _choices(a: RunData, b: RunData) -> dict[str, Any] | None:
    """Which choice matched applicants got: each choice's share of the matched applicants, in A and in B."""
    payloads = _both(lambda data: matched_choice(data.run.metrics or {}), a, b)
    if payloads is None:
        return None

    def pairs(payload: Payload) -> Pairs:
        return [(count, sum(payload["counts"])) for count in payload["counts"]]

    labels, names = payloads[0]["labels"], payloads[0]["names"]
    chart = _versus(labels, names, "matched applicants", pairs(payloads[0]), pairs(payloads[1]), whole=False)
    mine, theirs = (run["values"] for run in chart["payload"]["runs"])
    top3 = [sum(payload["counts"][:3]) / sum(payload["counts"]) for payload in payloads]
    chart["summary"] = (
        f"Of the matched applicants, {_percent(mine[0])} got their first choice in A and {_percent(theirs[0])} in B "
        f"({difference(mine[0], theirs[0], 'share')}); {_percent(top3[0])} and {_percent(top3[1])} got one of their "
        "first three."
    )
    chart["head"] = "Choice"
    return chart


def _interviews(a: RunData, b: RunData) -> dict[str, Any] | None:
    """Who gets the interviews: the share of applicants with each number of interviews, in A and in B.

    The run whose applicants had more interviews sets the bars; the other has none in the numbers it never reached.
    """
    payloads = _both(interviews_per_applicant, a, b)
    if payloads is None:
        return None
    longer = max(payloads, key=lambda payload: len(payload["labels"]))

    def pairs(payload: Payload) -> Pairs:
        counts = payload["counts"] + [0] * (len(longer["labels"]) - len(payload["counts"]))
        return [(count, sum(counts)) for count in counts]

    sides = pairs(payloads[0]), pairs(payloads[1])
    chart = _versus(longer["labels"], longer["names"], "applicants", *sides, whole=False)
    mine, theirs = (run["values"] for run in chart["payload"]["runs"])
    chart["summary"] = (
        f"Applicants had {payloads[0]['mean']:.1f} interviews on average in A and {payloads[1]['mean']:.1f} in B; "
        f"{_percent(mine[0])} and {_percent(theirs[0])} had none."
    )
    chart["head"] = "Interviews"
    return chart


def _fill(a: RunData, b: RunData) -> dict[str, Any] | None:
    """Which programs fill: the share of positions filled in each fifth of programs by quality, in A and in B."""
    payloads = _both(program_fill, a, b)
    if payloads is None:
        return None

    def pairs(payload: Payload) -> Pairs:
        filled, unfilled = (series["counts"] for series in payload["series"])
        return [(taken, taken + free) for taken, free in zip(filled, unfilled, strict=True)]

    sides = pairs(payloads[0]), pairs(payloads[1])
    chart = _versus(payloads[0]["labels"], payloads[0]["names"], "positions", *sides, whole=True)
    mine, theirs = (run["values"] for run in chart["payload"]["runs"])
    overall = [_ratio(sum(count for count, _ in side), sum(total for _, total in side)) for side in sides]
    bottom, top = STRENGTH_BANDS[0].lower(), STRENGTH_BANDS[-1].lower()
    chart["summary"] = (
        f"A filled {_percent(overall[0])} of its positions and B {_percent(overall[1])}. Programs in the {bottom} by "
        f"quality filled {_percent(mine[0])} of theirs in A and {_percent(theirs[0])} in B; those in the {top}, "
        f"{_percent(mine[-1])} and {_percent(theirs[-1])}."
    )
    chart["head"] = "Programs by quality"
    return chart


def comparison_charts(a: RunData, b: RunData) -> dict[str, Any]:
    """Return the comparison's charts: each run's "who matched where", and four charts with both runs.

    A chart that either run has no data for is left out.
    """
    charts: dict[str, Any] = {
        "compare_strength": _strength(a, b),
        "compare_choice": _choices(a, b),
        "compare_interviews": _interviews(a, b),
        "compare_fill": _fill(a, b),
    }
    for side, data in (("a", a), ("b", b)):
        charts[f"sorting_{side}"] = run_charts(data, ("sorting",))["sorting"]
    return {key: chart for key, chart in charts.items() if chart}
