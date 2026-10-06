"""Saved example runs: runs kept in the repository and shown to everyone at /examples/ (nrmps.example_views).

An example is one run of a preset with a fixed seed, saved as files in nrmps/example_runs/<slug>/ in the format of
`manage.py nrmp_run --out`: params.json (with the seed), population.npz, results.npz (the per-agent pre-interview
results), stages.npz (the decisions from applications to the match) and metrics.json (the diagnostics with the
version stamps, and each stage's time and counts). `manage.py nrmp_examples` writes them.

Their pages are a run's own pages (nrmps.run_views), read-only, open to visitors and offered to search engines.
They never touch the database: `saved_run` builds, once per process, a SimulationRun that is not stored (with its
simulation and stages) and its RunData from the files. Everyone therefore sees the same market every time, and a
change of the engine cannot change what they see unnoticed: `stale` compares the files with what the code gives
now, and the tests fail until the examples are saved again.
"""

import json
import math
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from .charts import run_charts
from .engine.persistence import (
    population_digest,
    population_to_npz,
    read_npz,
    results_to_npz,
    stage_record,
    stages_to_npz,
)
from .engine.pipeline import run_pipeline
from .engine.population import generate_population
from .models import RunArtifact, Simulation, SimulationRun, Stage, StageRun
from .params import load_params
from .presets import preset_params
from .runs import RunData, fingerprints
from .versions import stamps

DIRECTORY = Path(__file__).resolve().parent / "example_runs"
GENERATED = {"applicants": "generated", "programs": "generated"}
# The array files of a saved run, as `manage.py nrmp_run --out` names them, and the artifact each one holds.
ARRAY_FILES = {
    "population.npz": RunArtifact.Kind.POPULATION,
    "results.npz": RunArtifact.Kind.PRE_INTERVIEW,
    "stages.npz": RunArtifact.Kind.STAGES,
}
FILES = ("params.json", *ARRAY_FILES, "metrics.json")
# What may differ between a saved run and the same run computed now: when and where it was computed, and how fast.
# The population's digest is among them: it hashes the numbers' bytes, and a processor of another make may round the
# last bit of one differently (the arrays themselves are compared, within rounding).
VOLATILE = ("saved_at", "duration_ms", "population_digest")
VOLATILE_STAMPS = ("app_version", "git_sha", "numpy_version", "python_version")
# Their labels, as on the tabs of a run's pages (nrmps.run_views.RUN_TABS; the tests keep the two alike).
PAGE_LABELS = {
    "summary": "Summary",
    "population": "Population",
    "pre_interview": "Before interviews",
    "applications": "Applications and interviews",
    "match": "Match",
}
# The pairs file (one row per applicant and program) is offered up to this many pairs.
PAIRS_DOWNLOAD_LIMIT = 50_000


@dataclass(frozen=True)
class Example:
    """A saved example run: the preset and seed it is a run of, and how its pages present it."""

    slug: str  # in the address: /examples/<slug>/
    preset: str  # a key of nrmps.presets.PRESETS, also offered by "Try a demo"
    seed: int
    name: str  # as a heading
    phrase: str  # in a sentence
    lead: str  # what the market is
    highlights: tuple[tuple[str, str], ...]  # what to look at: (a page's key, a sentence)


EXAMPLES: dict[str, Example] = {
    example.slug: example
    for example in (
        Example(
            slug="nrmp-like-market",
            preset="nrmp_like",
            seed=2026,
            name="NRMP-like market",
            phrase="the NRMP-like market",
            lead=(
                "The simulator's default market. Applicants come in five groups, in proportions like those of the "
                "Main Residency Match (US MD seniors, US DO seniors, US and non-US international medical graduates, "
                "and others), and there are slightly fewer positions than applicants. Applicants agree only "
                "moderately on which programs are best, as programs do on applicants, and each side sees the other "
                "through noise before interviews."
            ),
            highlights=(
                ("match", "Who matched, by applicant group and by strength, and which choice on their list they got."),
                ("applications", "How the interviews are spread: who holds many, and who has none."),
                ("pre_interview", "How well each side can judge the other before interviews."),
                ("population", "The applicant groups and the programs the market was generated with."),
            ),
        ),
        Example(
            slug="small-classroom-market",
            preset="classroom",
            seed=2026,
            name="Small classroom market",
            phrase="the small classroom market",
            lead=(
                "The same model in a market small enough to follow by hand: 60 applicants and 8 programs. Open any "
                "applicant or program to see every application, interview invitation, interview and rank, and how "
                "the match came out."
            ),
            highlights=(
                ("applicants", "Follow one applicant from their applications to the match."),
                ("programs", "See whom a program invited, how it ranked them and who filled its positions."),
                ("applications", "Every application in one table, from the invitation to the match."),
                ("match", "Which choice each applicant got, and who was left unmatched."),
            ),
        ),
    )
}


@dataclass(eq=False)
class SavedRun:
    """An example's run as its pages use it. Nothing of it is in the database."""

    example: Example
    run: SimulationRun
    data: RunData
    stages: list[StageRun]
    _charts: dict[tuple[str, ...], dict[str, Any]] = field(default_factory=dict, repr=False)

    def charts(self, names: tuple[str, ...]) -> dict[str, Any]:
        """Return the charts `names` (nrmps.charts.run_charts), computed once per process: the run never changes."""
        if names not in self._charts:
            self._charts[names] = run_charts(self.data, names)
        return self._charts[names]

    @property
    def pairs_download(self) -> bool:
        """Return True if the run is small enough to offer its pairs file to everyone."""
        return self.run.n_pairs <= PAIRS_DOWNLOAD_LIMIT


def _json(data: Any, *, sort_keys: bool = False) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=sort_keys) + "\n").encode()


def build(example: Example) -> dict[str, bytes]:
    """Run the example's market with the code as it is now and return the contents of its files."""
    params = preset_params(example.preset, seed=example.seed)
    started = clock = time.perf_counter()
    population = generate_population(params, example.seed)
    stages: list[dict[str, Any]] = []

    def record_stage(stage: str, seconds: float, counts: dict[str, int]) -> None:
        stages.append({"stage": stage, "duration_ms": round(seconds * 1000), "counts": counts})

    counts = {
        "applicants": population.n_applicants,
        "programs": population.n_programs,
        "positions": population.n_positions,
    }
    record_stage(Stage.POPULATION.value, time.perf_counter() - clock, counts)
    result = run_pipeline(params, example.seed, population=population, on_stage=record_stage)
    record = {
        "seed": example.seed,
        "params_hash": params.params_hash(),
        "population_digest": population_digest(population),
        "fingerprints": fingerprints(params, example.seed, GENERATED),
        "stamps": stamps(),
        "saved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "stages": stages,
        "metrics": result.metrics,
    }
    return {
        "params.json": _json(params.to_json_data()),
        "population.npz": population_to_npz(population),
        "results.npz": results_to_npz(result.pre.applicants, result.pre.programs),
        "stages.npz": stages_to_npz(stage_record(result)),
        "metrics.json": _json(record, sort_keys=True),
    }


def _close(a: Any, b: Any) -> bool:
    """Return True if two JSON values are equal, with numbers equal within rounding."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[key], b[key]) for key in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float) and isinstance(b, int | float) and not isinstance(b, bool):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    if isinstance(b, float) and isinstance(a, int) and not isinstance(a, bool):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return bool(a == b)


def _same_arrays(saved: bytes, built: bytes) -> bool:
    """Return True if two npz files hold the same arrays: decisions equal, numbers equal within rounding."""
    (arrays, meta), (new_arrays, new_meta) = read_npz(saved), read_npz(built)
    if meta != new_meta or arrays.keys() != new_arrays.keys():
        return False
    for name, array in arrays.items():
        other = new_arrays[name]
        if array.dtype != other.dtype or array.shape != other.shape:
            return False
        if array.dtype.kind == "f":
            if not np.allclose(array, other, rtol=1e-9, atol=1e-12, equal_nan=True):
                return False
        elif not np.array_equal(array, other):
            return False
    return True


def _lasting(record: dict[str, Any]) -> dict[str, Any]:
    """Return a saved run's record without what differs from one computation to the next."""
    lasting = {key: value for key, value in record.items() if key not in VOLATILE}
    lasting["stamps"] = {key: value for key, value in record["stamps"].items() if key not in VOLATILE_STAMPS}
    lasting["stages"] = [
        {key: value for key, value in stage.items() if key != "duration_ms"} for stage in record["stages"]
    ]
    return lasting


def _differences(example: Example, built: dict[str, bytes]) -> list[str]:
    folder = DIRECTORY / example.slug
    missing = [name for name in FILES if not (folder / name).is_file()]
    if missing:
        return [f"{name} is missing" for name in missing]
    changed = []
    if json.loads((folder / "params.json").read_bytes()) != json.loads(built["params.json"]):
        changed.append("params.json")
    changed += [name for name in ARRAY_FILES if not _same_arrays((folder / name).read_bytes(), built[name])]
    saved_record = _lasting(json.loads((folder / "metrics.json").read_bytes()))
    if not _close(saved_record, _lasting(json.loads(built["metrics.json"]))):
        changed.append("metrics.json")
    return [f"{name} differs" for name in changed]


def stale(example: Example) -> list[str]:
    """Return what differs between the example's saved files and what the code gives now (nothing: up to date).

    Decisions and counts must be equal and numbers equal within rounding (another make of processor may round the
    last bit differently). When and where the run was computed and how long it took may differ: the date, the times,
    the population's digest and the version stamps other than the model's, the engine's and the schema's.
    """
    return _differences(example, build(example))


def save(example: Example, *, force: bool = False) -> list[str]:
    """Save the example's run again if it is out of date (or `force`), and return what had changed."""
    built = build(example)
    changed = _differences(example, built)
    if changed or force:
        folder = DIRECTORY / example.slug
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in built.items():
            (folder / name).write_bytes(data)
        saved_run.cache_clear()
    return changed


@cache
def saved_run(slug: str) -> SavedRun:
    """Return example `slug`'s saved run, loaded from its files once per process.

    Raises KeyError if there is no such example. The run, its simulation and its stages are model instances that are
    never stored, so the pages of a user's run can show them.
    """
    example = EXAMPLES[slug]
    folder = DIRECTORY / slug
    record = json.loads((folder / "metrics.json").read_bytes())
    params = load_params(json.loads((folder / "params.json").read_bytes())).to_json_data()
    market = record["metrics"]["market"]
    saved_at = datetime.fromisoformat(record["saved_at"])
    run = SimulationRun(
        simulation=Simulation(name=example.name, description=example.lead, params=params),
        number=1,
        status=SimulationRun.Status.SUCCEEDED,
        created_at=saved_at,
        finished_at=saved_at,
        duration_ms=record["duration_ms"],
        params=params,
        params_hash=record["params_hash"],
        seed=record["seed"],
        population_source=dict(GENERATED),
        population_digest=record["population_digest"],
        fingerprints=record["fingerprints"],
        n_applicants=market["n_applicants"],
        n_programs=market["n_programs"],
        n_positions=market["n_positions"],
        metrics=record["metrics"],
        **record["stamps"],
    )
    stages = [
        StageRun(
            run=run,
            stage=stage["stage"],
            status=SimulationRun.Status.SUCCEEDED,
            fingerprint=record["fingerprints"].get(stage["stage"], ""),
            duration_ms=stage["duration_ms"],
            counts=stage["counts"],
        )
        for stage in record["stages"]
    ]
    artifacts = {str(kind): (folder / name).read_bytes() for name, kind in ARRAY_FILES.items()}
    return SavedRun(example, run, RunData(run, artifacts), stages)


def saved_runs() -> list[SavedRun]:
    """Return every example's saved run, in the order of EXAMPLES."""
    return [saved_run(slug) for slug in EXAMPLES]


# --- What search engines show (nrmps.seo) -----------------------------------------------------------------------------

PAGE_TITLES = {
    "summary": "a saved run of a simulated Match",
    "population": "applicants, programs and positions",
    "pre_interview": "preferences before interviews",
    "applications": "applications and interviews",
    "match": "who matched, and where",
}


def page_title(example: Example, page: str) -> str:
    """Return the title of one of the example's indexed pages, for a search result."""
    return f"{example.name}: {PAGE_TITLES[page]}"


def page_description(saved: SavedRun, page: str) -> str:
    """Return the description of one of the example's indexed pages, for a search result, with the run's numbers."""
    run, phrase = saved.run, saved.example.phrase
    match = (run.metrics or {})["outcomes"]["match"]
    counts = {stage.stage: stage.counts for stage in saved.stages}
    if page == "summary":
        return (
            f"One saved run of {phrase}: {run.n_applicants:,} applicants, {run.n_programs:,} programs and "
            f"{run.n_positions:,} positions, from applications and interviews to the match. No account needed."
        )
    if page == "population":
        return (
            f"The {run.n_applicants:,} applicants and {run.n_programs:,} programs of {phrase} in a saved run: "
            "applicant groups, strength, program quality and positions per program."
        )
    if page == "pre_interview":
        return (
            f"Before interviews in a saved run of {phrase}: how alike preferences are, how well each side sees "
            "the other, and the most wanted programs."
        )
    if page == "applications":
        return (
            f"{counts['applications']['applications']:,} applications and {counts['interviews']['interviews']:,} "
            f"interviews in a saved run of {phrase}: the funnel from application to rank order list, and who "
            "gets the interviews."
        )
    if page == "match":
        filled = "every position" if match["fill_rate"] >= 1 else f"{match['fill_rate']:.1%} of positions"
        return (
            f"In a saved run of {phrase}, {match['matched']:,} of {match['certified']:,} applicants with a rank "
            f"order list matched ({match['match_rate']:.1%}) and {filled} filled."
        )
    raise KeyError(page)
