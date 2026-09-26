"""Starting and executing simulation runs, and loading their results (plan steps 2.3-2.5).

`start_run` freezes everything a run depends on: the validated parameters with the seed, the version stamps and the
population (generated, uploaded or both), which it stores as an artifact. `execute_run` computes the pre-interview
stage from that population and stores the per-agent results and the diagnostics. Pair-level values are not stored;
`RunData` recomputes them for the pages that show them.
"""

import hashlib
import logging
import secrets
import time
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from typing import Any

import numpy as np
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from numpy.typing import NDArray
from pydantic import ValidationError

from .engine import MODEL_VERSION
from .engine.persistence import (
    population_digest,
    population_from_npz,
    population_to_npz,
    results_from_npz,
    results_to_npz,
)
from .engine.pipeline import SideResult, blocks, run_pre_interview, side_block
from .engine.population import Population, PopulationError, generate_population
from .engine.utility import MarketModel, build_market
from .exceptions import SimulationError
from .limits import check_market_size
from .models import IMPLEMENTED_STAGES, PopulationUpload, RunArtifact, Simulation, SimulationRun, Stage, StageRun
from .params import SimulationParams, canonical_json, stage_inputs
from .population_csv import UploadedSide, applicant_side, program_side
from .versions import stamps

logger = logging.getLogger(__name__)

Status = SimulationRun.Status


class RunInProgressError(SimulationError):
    """The simulation already has a queued or running run."""

    def __init__(self) -> None:
        super().__init__("A run of this simulation is already queued or running. Wait for it to finish.")


def fingerprints(params: SimulationParams, seed: int, sources: dict[str, str]) -> dict[str, str]:
    """Return, per implemented stage, a hash of everything the stage depends on.

    A stage depends on the model version, the seed, the parameters it reads and its upstream stage; the population
    also depends on where each side comes from (generated, or the digest of an uploaded file).
    """
    result: dict[str, str] = {}
    upstream = ""
    for stage in IMPLEMENTED_STAGES:
        data: dict[str, Any] = {
            "model_version": MODEL_VERSION,
            "stage": stage.value,
            "seed": seed,
            "inputs": stage_inputs(params, stage.value),
            "upstream": upstream,
        }
        if stage == Stage.POPULATION:
            data["sources"] = sources
        upstream = result[stage.value] = hashlib.sha256(canonical_json(data).encode()).hexdigest()
    return result


def upload_sources(uploads: dict[str, PopulationUpload]) -> dict[str, str]:
    """Return where each side comes from, as the population fingerprint sees it."""
    return {side: uploads[side].digest if side in uploads else "generated" for side in ("applicants", "programs")}


def build_population(
    params: SimulationParams, seed: int, uploads: dict[str, PopulationUpload]
) -> tuple[Population, dict[str, str]]:
    """Return the population for a run (uploaded sides as given, the rest generated) and each side's source label.

    Raises PopulationError if an upload does not fit the parameters.
    """
    applicants = programs = None
    labels = {"applicants": "generated", "programs": "generated"}
    if upload := uploads.get("applicants"):
        applicants = applicant_side(UploadedSide.from_npz(bytes(upload.data)), params, seed)
        labels["applicants"] = upload.filename or "uploaded file"
    if upload := uploads.get("programs"):
        programs = program_side(UploadedSide.from_npz(bytes(upload.data)), params, seed)
        labels["programs"] = upload.filename or "uploaded file"
    return generate_population(params, seed, applicants=applicants, programs=programs), labels


def _milliseconds(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _save_artifact(run: SimulationRun, kind: str, data: bytes) -> None:
    RunArtifact.objects.create(run=run, kind=kind, data=data, size=len(data), sha256=hashlib.sha256(data).hexdigest())


def start_run(simulation: Simulation, user: Any = None) -> SimulationRun:
    """Create a queued run of the simulation's current parameters and store its population.

    Raises SimulationError (with a message for the user) if the parameters or an uploaded population do not work,
    if the market is above the size limit, or if another run is queued or running.
    """
    try:
        with transaction.atomic():
            simulation.lock()
            if simulation.runs.filter(status__in=SimulationRun.ACTIVE).exists():
                raise RunInProgressError()
            try:
                params = simulation.get_params()
            except ValidationError as exc:
                raise SimulationError("The saved parameters are not valid. Open them, fix them and save.") from exc
            drawn = params.run.seed is None
            seed = secrets.randbits(63) if drawn else int(params.run.seed or 0)
            params = params.with_seed(seed)
            uploads = {upload.side: upload for upload in simulation.uploads.all()}
            started = time.perf_counter()
            try:
                population, labels = build_population(params, seed, uploads)
            except PopulationError as exc:
                raise SimulationError(str(exc)) from exc
            check_market_size(population.n_applicants, population.n_programs)
            data = population_to_npz(population)
            population_ms = _milliseconds(started)
            number = (simulation.runs.aggregate(Max("number"))["number__max"] or 0) + 1
            prints = fingerprints(params, seed, upload_sources(uploads))
            pairs = population.n_applicants * population.n_programs
            run = SimulationRun.objects.create(
                simulation=simulation,
                number=number,
                created_by=user if getattr(user, "is_authenticated", False) else None,
                params=params.to_json_data(),
                params_hash=params.params_hash(),
                seed=seed,
                seed_was_drawn=drawn,
                population_source=labels,
                population_digest=population_digest(population),
                fingerprints=prints,
                n_applicants=population.n_applicants,
                n_programs=population.n_programs,
                n_positions=population.n_positions,
                progress_total=2 * pairs,
                **stamps(),
            )
            _save_artifact(run, RunArtifact.Kind.POPULATION, data)
            now = timezone.now()
            StageRun.objects.create(
                run=run,
                stage=Stage.POPULATION,
                status=Status.SUCCEEDED,
                fingerprint=prints[Stage.POPULATION],
                started_at=now,
                finished_at=now,
                duration_ms=population_ms,
                counts={
                    "applicants": population.n_applicants,
                    "programs": population.n_programs,
                    "positions": population.n_positions,
                },
            )
    except IntegrityError as exc:  # a concurrent request created a run first
        raise RunInProgressError() from exc
    return run


def execute_run(run_id: int) -> SimulationRun:
    """Compute a queued run's pre-interview stage and store the results; return the updated run.

    Problems with the data are recorded on the run (status failed, with the message); unexpected errors are logged
    and recorded with a generic message. A run that is not queued is left alone.
    """
    run = SimulationRun.objects.get(pk=run_id)
    now = timezone.now()
    if not SimulationRun.objects.filter(pk=run_id, status=Status.QUEUED).update(status=Status.RUNNING, started_at=now):
        run.refresh_from_db()
        return run
    started = time.perf_counter()
    last_update = 0.0

    def progress(done: int, total: int) -> None:
        nonlocal last_update
        moment = time.monotonic()
        if moment - last_update >= 0.5 or done == total:
            last_update = moment
            SimulationRun.objects.filter(pk=run_id).update(progress_done=done)

    try:
        params = run.get_params()
        population_data = run.artifact(RunArtifact.Kind.POPULATION)
        if population_data is None:
            raise PopulationError("The run has no stored population.")
        result = run_pre_interview(
            params,
            run.seed,
            replicate=run.replicate,
            population=population_from_npz(population_data),
            block_pairs=settings.NRMP_BLOCK_PAIRS,
            progress=progress,
        )
        results = results_to_npz(result.applicants, result.programs)
    except Exception as exc:  # recorded on the run; the page shows it
        if isinstance(exc, ValueError):
            message = str(exc)
            logger.info("Run failed run_id=%s: %s", run_id, message)
        else:
            message = "The run failed unexpectedly. The error has been logged; please try again or report it."
            logger.exception("Run failed unexpectedly run_id=%s", run_id)
        _finish(run, Status.FAILED, started, error=message)
        return SimulationRun.objects.get(pk=run_id)
    _finish(run, Status.SUCCEEDED, started, metrics=result.metrics, results=results)
    return SimulationRun.objects.get(pk=run_id)


def _finish(
    run: SimulationRun,
    status: str,
    started: float,
    *,
    error: str = "",
    metrics: dict[str, Any] | None = None,
    results: bytes | None = None,
) -> None:
    """Record the pre-interview stage and the run's outcome in one transaction."""
    duration = _milliseconds(started)
    finished = timezone.now()
    with transaction.atomic():
        if results is not None:
            _save_artifact(run, RunArtifact.Kind.PRE_INTERVIEW, results)
        StageRun.objects.create(
            run=run,
            stage=Stage.PRE_INTERVIEW,
            status=status,
            fingerprint=run.fingerprints.get(Stage.PRE_INTERVIEW, ""),
            started_at=run.started_at or finished,
            finished_at=finished,
            duration_ms=duration,
            counts={"pairs": run.n_pairs} if status == Status.SUCCEEDED else {},
            error=error,
        )
        population_ms = run.stages.filter(stage=Stage.POPULATION).values_list("duration_ms", flat=True).first() or 0
        updates: dict[str, Any] = {
            "status": status,
            "finished_at": finished,
            "duration_ms": population_ms + duration,
            "error": error,
        }
        if metrics is not None:
            updates |= {"metrics": metrics, "progress_done": run.progress_total}
        SimulationRun.objects.filter(pk=run.pk).update(**updates)


def run_now(simulation: Simulation, user: Any = None) -> SimulationRun:
    """Start a run and execute it in this process (until background jobs exist)."""
    run = start_run(simulation, user)
    return execute_run(run.pk)


# --- Results ----------------------------------------------------------------------------------------------------------


@dataclass
class PairRows:
    """One agent's pair-level values over every target, with the other side's view of the same pairs."""

    true: NDArray[np.float64]
    observed: NDArray[np.float64]
    true_rank: NDArray[np.int32]
    observed_rank: NDArray[np.int32]
    other_true: NDArray[np.float64]  # the targets' true utility for this agent
    other_observed: NDArray[np.float64]
    other_true_rank: NDArray[np.int32] | None  # where the targets rank this agent (None above the drill-down limit)
    other_observed_rank: NDArray[np.int32] | None


class RunData:
    """A finished run's population, per-agent results and market model, loaded from its artifacts."""

    def __init__(self, run: SimulationRun):
        self.run = run
        self.params = run.get_params()
        population_data = run.artifact(RunArtifact.Kind.POPULATION)
        if population_data is None:
            raise PopulationError("The run has no stored population.")
        self.population = population_from_npz(population_data)
        results = run.artifact(RunArtifact.Kind.PRE_INTERVIEW)
        self.applicant_results: SideResult | None = None
        self.program_results: SideResult | None = None
        if results is not None:
            self.applicant_results, self.program_results = results_from_npz(results)

    @cached_property
    def model(self) -> MarketModel:
        """Return the market model (per-agent terms); pair values are computed from it on demand."""
        return build_market(self.params, self.population, self.run.seed, self.run.replicate)

    @property
    def drilldown_ranks(self) -> bool:
        """Return True if the other side's ranks may be computed for a page (they need every pair)."""
        return self.run.n_pairs <= settings.NRMP_DRILLDOWN_MAX_PAIRS

    def _column_ranks(self, applicants: bool, column: int) -> tuple[NDArray[np.int32], NDArray[np.int32]]:
        """Return, for every agent of one side, the true and observed rank it gives target `column`."""
        side, view = (
            (self.model.applicants, self.model.applicant_view)
            if applicants
            else (self.model.programs, self.model.program_view)
        )
        true = np.empty(side.n_agents, dtype=np.int32)
        observed = np.empty(side.n_agents, dtype=np.int32)
        for agents in blocks(side.n_agents, settings.NRMP_BLOCK_PAIRS // max(1, side.n_targets)):
            _t, _o, true_ranks, observed_ranks = side_block(side, view, agents, self.run.replicate)
            true[agents] = true_ranks[:, column]
            observed[agents] = observed_ranks[:, column]
        return true, observed

    def applicant_rows(self, i: int) -> PairRows:
        """Return applicant i's view of every program, and every program's view of applicant i."""
        return self._rows(i, applicant=True)

    def program_rows(self, j: int) -> PairRows:
        """Return program j's view of every applicant, and every applicant's view of program j."""
        return self._rows(j, applicant=False)

    def _rows(self, agent: int, *, applicant: bool) -> PairRows:
        model = self.model
        side, view = (model.applicants, model.applicant_view) if applicant else (model.programs, model.program_view)
        other, other_view = (
            (model.programs, model.program_view) if applicant else (model.applicants, model.applicant_view)
        )
        me = np.array([agent], dtype=np.int64)
        true, observed, true_rank, observed_rank = side_block(side, view, me, self.run.replicate)
        everyone = np.arange(other.n_agents, dtype=np.int64)
        values = other.utilities(everyone, me)
        other_true = values[:, 0]
        other_observed = other_view.observe(values, everyone, me)[:, 0]
        other_true_rank = other_observed_rank = None
        if self.drilldown_ranks:
            other_true_rank, other_observed_rank = self._column_ranks(not applicant, agent)
        return PairRows(
            true=true[0],
            observed=observed[0],
            true_rank=true_rank[0],
            observed_rank=observed_rank[0],
            other_true=other_true,
            other_observed=other_observed,
            other_true_rank=other_true_rank,
            other_observed_rank=other_observed_rank,
        )

    def pair_rows(self) -> Iterator[list[Any]]:
        """Yield one row per applicant-program pair (applicant-major) with both sides' values and ranks."""
        model = self.model
        population = self.population
        replicate = self.run.replicate
        n, m = population.n_applicants, population.n_programs
        program_true = np.empty((m, n), dtype=np.int32)
        program_observed = np.empty((m, n), dtype=np.int32)
        for agents in blocks(m, settings.NRMP_BLOCK_PAIRS // max(1, n)):
            _t, _o, true_ranks, observed_ranks = side_block(model.programs, model.program_view, agents, replicate)
            program_true[agents] = true_ranks
            program_observed[agents] = observed_ranks
        programs = np.arange(m, dtype=np.int64)
        for applicants in blocks(n, settings.NRMP_BLOCK_PAIRS // max(1, m)):
            u, u_hat, u_rank, u_hat_rank = side_block(model.applicants, model.applicant_view, applicants, replicate)
            v = model.programs.utilities(programs, applicants)
            v_hat = model.program_view.observe(v, programs, applicants)
            for row, i in enumerate(applicants):
                name = population.applicants.name(int(i))
                for j in range(m):
                    yield [
                        name,
                        population.programs.name(j),
                        repr(float(u[row, j])),
                        repr(float(u_hat[row, j])),
                        int(u_rank[row, j]),
                        int(u_hat_rank[row, j]),
                        repr(float(v[j, row])),
                        repr(float(v_hat[j, row])),
                        int(program_true[j, i]),
                        int(program_observed[j, i]),
                    ]


PAIR_COLUMNS = [
    "applicant",
    "program",
    "applicant_true_utility",
    "applicant_pre_interview_score",
    "applicant_true_rank",
    "applicant_pre_interview_rank",
    "program_true_utility",
    "program_pre_interview_score",
    "program_true_rank",
    "program_pre_interview_rank",
]
