"""Starting and executing simulation runs, and loading their results (plan steps 2.3-2.5 and 3.7).

`start_run` freezes everything a run depends on: the validated parameters with the seed, the version stamps and the
population (generated, uploaded or both), which it stores as an artifact. `execute_run` computes every later stage,
from the pre-interview views to the match, and stores the per-agent pre-interview results, the decisions of each
stage (applications, signals, invitations, interviews, rank order lists and the match) and the diagnostics.
Continuous pair values are not stored; `RunData` recomputes them for the pages and downloads that show them.
"""

import hashlib
import logging
import secrets
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property
from typing import Any

import logfire
import numpy as np
from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from numpy.typing import NDArray
from pydantic import ValidationError

from .engine import MODEL_VERSION
from .engine.applications import REACH, SAFETY, TARGET
from .engine.interviews import pair_views
from .engine.persistence import (
    StageRecord,
    population_digest,
    population_from_npz,
    population_to_npz,
    results_from_npz,
    results_to_npz,
    stage_record,
    stages_from_npz,
    stages_to_npz,
)
from .engine.pipeline import SideResult, blocks, run_pipeline, side_block
from .engine.population import Population, PopulationError, generate_population
from .engine.utility import MarketModel, build_market
from .exceptions import SimulationError
from .limits import check_market_size
from .models import (
    IMPLEMENTED_STAGES,
    PopulationUpload,
    RunArtifact,
    Simulation,
    SimulationRun,
    Stage,
    StageRun,
    WorkerHeartbeat,
)
from .params import SimulationParams, canonical_json, stage_inputs
from .population_csv import UploadedSide, applicant_side, program_side
from .quotas import check_run_quota
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


def start_run(simulation: Simulation, user: Any = None, *, notify: bool = False) -> SimulationRun:
    """Create a queued run of the simulation's current parameters and store its population.

    Raises SimulationError (with a message for the user) if the parameters or an uploaded population do not work,
    if the market is above the size limit, if the account has reached a quota, or if another run is queued or
    running. `notify` asks for an email when the run finishes.
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
                with logfire.span("population stage", simulation_id=simulation.pk, seed=seed):
                    population, labels = build_population(params, seed, uploads)
            except PopulationError as exc:
                raise SimulationError(str(exc)) from exc
            check_market_size(population.n_applicants, population.n_programs)
            check_run_quota(user, population.n_applicants * population.n_programs)
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
                notify_email=notify,
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


@dataclass
class StageReport:
    """A finished stage as the engine reported it."""

    stage: str
    milliseconds: int
    counts: dict[str, int]


def execute_run(run_id: int) -> SimulationRun:
    """Compute a queued run's stages, from the pre-interview views to the match, and store the results.

    Each stage is recorded as it finishes, so the run's page shows how far it has got. Problems with the data are
    recorded on the run (status failed, with the message, on the stage that failed); unexpected errors are logged and
    recorded with a generic message. A run that is not queued is left alone.
    """
    run = SimulationRun.objects.get(pk=run_id)
    now = timezone.now()
    if not SimulationRun.objects.filter(pk=run_id, status=Status.QUEUED).update(status=Status.RUNNING, started_at=now):
        run.refresh_from_db()
        return run
    started = time.perf_counter()
    last_update = 0.0
    reports: list[StageReport] = []
    stage_started = now

    def progress(done: int, total: int) -> None:
        nonlocal last_update
        moment = time.monotonic()
        if moment - last_update >= 0.5 or done == total:
            last_update = moment
            SimulationRun.objects.filter(pk=run_id).update(progress_done=done)

    def on_stage(stage: str, seconds: float, counts: dict[str, int]) -> None:
        nonlocal stage_started
        report = StageReport(stage, round(seconds * 1000), counts)
        finished = timezone.now()
        StageRun.objects.create(
            run=run,
            stage=stage,
            status=Status.SUCCEEDED,
            fingerprint=run.fingerprints.get(stage, ""),
            started_at=stage_started,
            finished_at=finished,
            duration_ms=report.milliseconds,
            counts=counts,
        )
        reports.append(report)
        stage_started = finished

    try:
        params = run.get_params()
        population_data = run.artifact(RunArtifact.Kind.POPULATION)
        if population_data is None:
            raise PopulationError("The run has no stored population.")
        with logfire.span(
            "run stages", run_id=run_id, n_applicants=run.n_applicants, n_programs=run.n_programs, n_pairs=run.n_pairs
        ):
            result = run_pipeline(
                params,
                run.seed,
                replicate=run.replicate,
                population=population_from_npz(population_data),
                block_pairs=settings.NRMP_BLOCK_PAIRS,
                progress=progress,
                on_stage=on_stage,
            )
            artifacts: dict[str, bytes] = {
                RunArtifact.Kind.PRE_INTERVIEW: results_to_npz(result.pre.applicants, result.pre.programs),
                RunArtifact.Kind.STAGES: stages_to_npz(stage_record(result)),
            }
        if result.match.blocking_pairs:  # impossible for deferred acceptance; recorded rather than hidden
            logger.error("Unstable match run_id=%s blocking_pairs=%s", run_id, result.match.blocking_pairs)
    except Exception as exc:  # recorded on the run; the page shows it
        if isinstance(exc, ValueError):
            message = str(exc)
            logger.info("Run failed run_id=%s: %s", run_id, message)
        else:
            message = "The run failed unexpectedly. The error has been logged; please try again or report it."
            logger.exception("Run failed unexpectedly run_id=%s", run_id)
        _finish(run, Status.FAILED, started, reports, error=message, failed_since=stage_started)
        return _notify(SimulationRun.objects.get(pk=run_id))
    _finish(run, Status.SUCCEEDED, started, reports, metrics=result.metrics, artifacts=artifacts)
    return _notify(SimulationRun.objects.get(pk=run_id))


def _notify(run: SimulationRun) -> SimulationRun:
    """Email the run's owner that it finished, if they asked and their address is confirmed."""
    user = run.created_by
    if not run.notify_email or user is None or not user.email or not user.email_verified:
        return run
    path = reverse("nrmps:run_detail", kwargs={"pk": run.simulation_id, "number": run.number})
    context = {"run": run, "simulation": run.simulation, "link": f"{settings.SITE_URL}{path}"}
    outcome = "finished" if run.status == Status.SUCCEEDED else "failed"
    try:
        send_mail(
            subject=f"Run {run.number} of “{run.simulation.name}” {outcome}",
            message=render_to_string("emails/run_finished.txt", context),
            from_email=None,
            recipient_list=[user.email],
        )
    except OSError:
        logger.exception("Could not send the run-finished email run_id=%s", run.pk)
    return run


def _finish(
    run: SimulationRun,
    status: str,
    started: float,
    reports: list[StageReport],
    *,
    error: str = "",
    metrics: dict[str, Any] | None = None,
    artifacts: dict[str, bytes] | None = None,
    failed_since: datetime | None = None,
) -> None:
    """Record the run's outcome and results in one transaction; a failure lands on the first unfinished stage.

    The finished stages (`reports`) are already recorded: `execute_run` records each one as it finishes, and the
    failed stage started when the last of them finished (`failed_since`).
    """
    duration = _milliseconds(started)
    finished = timezone.now()
    with transaction.atomic():
        for kind, data in (artifacts or {}).items():
            _save_artifact(run, kind, data)
        if status == Status.FAILED:
            done = {report.stage for report in reports} | {Stage.POPULATION.value}
            failed = next(stage for stage in IMPLEMENTED_STAGES if stage.value not in done)
            StageRun.objects.create(
                run=run,
                stage=failed,
                status=Status.FAILED,
                fingerprint=run.fingerprints.get(failed.value, ""),
                started_at=failed_since or finished,
                finished_at=finished,
                duration_ms=duration - sum(report.milliseconds for report in reports),
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


def dispatch_run(run: SimulationRun) -> SimulationRun:
    """Hand a queued run to the task backend and return it refreshed.

    The immediate backend executes it before returning; the database backend queues it for the worker.
    """
    from .tasks import execute_run_task

    execute_run_task.enqueue(run.pk)
    run.refresh_from_db()
    return run


def run_now(simulation: Simulation, user: Any = None) -> SimulationRun:
    """Start a run and execute it in this process, whatever the task backend (commands and tests)."""
    run = start_run(simulation, user)
    return execute_run(run.pk)


def interrupt_stale_runs(older_than: timedelta) -> int:
    """Mark runs queued or running for longer than `older_than` as failed (their worker stopped); return how many."""
    cutoff = timezone.now() - older_than
    stale = SimulationRun.objects.filter(status__in=SimulationRun.ACTIVE, created_at__lt=cutoff)
    return stale.update(
        status=Status.FAILED,
        finished_at=timezone.now(),
        error="The run was interrupted before it finished (the worker stopped). Please run it again.",
    )


# --- Waiting runs -----------------------------------------------------------------------------------------------------

# A worker records a heartbeat every 30 seconds (manage.py nrmp_worker); one not seen for this long has stopped.
WORKER_STALE_SECONDS = 120


def worker_last_seen() -> int | None:
    """Return how many seconds ago a worker last recorded its heartbeat, or None if none ever did."""
    last = WorkerHeartbeat.objects.order_by("-last_seen").values_list("last_seen", flat=True).first()
    return None if last is None else round((timezone.now() - last).total_seconds())


@dataclass(frozen=True)
class RunWait:
    """Where a queued or running run stands, for its progress block: its stage, its wait and what may hold it up."""

    stage: str  # the stage in progress (running) or the next one to start (queued); "" once every stage finished
    ahead: int  # runs that start before this one: queued earlier, or running (queued runs only)
    worker_missing: bool  # runs wait for a worker here (TASK_BACKEND=database) and none has been seen lately
    too_long: bool  # queued for longer than NRMP_QUEUE_WARNING_SECONDS

    @property
    def warning(self) -> bool:
        """Return True if the page should warn that the run may not start or finish soon."""
        return self.worker_missing or self.too_long


def run_wait(run: SimulationRun) -> RunWait:
    """Return where a queued or running run stands: its current stage, how long it has waited and why."""
    queued = run.status == Status.QUEUED
    recorded = set(run.stages.values_list("stage", flat=True))
    stage = next((stage for stage in IMPLEMENTED_STAGES if stage.value not in recorded), None)
    ahead = 0
    if queued:
        ahead = (
            SimulationRun.objects.filter(
                Q(status=Status.RUNNING) | Q(status=Status.QUEUED, created_at__lt=run.created_at)
            )
            .exclude(pk=run.pk)
            .count()
        )
    background = settings.TASK_BACKEND == "database"
    last_seen = worker_last_seen() if background else None
    return RunWait(
        stage=str(stage.label) if stage else "",
        ahead=ahead,
        worker_missing=background and (last_seen is None or last_seen > WORKER_STALE_SECONDS),
        too_long=queued and (timezone.now() - run.created_at).total_seconds() > settings.NRMP_QUEUE_WARNING_SECONDS,
    )


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


@dataclass
class StageRows:
    """One agent's stage outcomes for every target (all programs, or all applicants), unset where none apply."""

    applied: NDArray[np.bool_]
    signal: NDArray[np.int8]  # signal tier, -1 = none
    wave: NDArray[np.int8]  # invitation wave, 0 = not invited
    interviewed: NDArray[np.bool_]
    post: NDArray[np.float64]  # the agent's post-interview view of the target (NaN without an interview)
    other_post: NDArray[np.float64]  # the target's post-interview view of the agent
    list_rank: NDArray[np.int32]  # the agent's list rank of the target (0 = not on the list)
    other_list_rank: NDArray[np.int32]  # the target's list rank of the agent
    matched: NDArray[np.bool_]

    @classmethod
    def empty(cls, n: int) -> StageRows:
        """Return rows for n targets with nothing applied."""
        return cls(
            applied=np.zeros(n, dtype=np.bool_),
            signal=np.full(n, -1, dtype=np.int8),
            wave=np.zeros(n, dtype=np.int8),
            interviewed=np.zeros(n, dtype=np.bool_),
            post=np.full(n, np.nan),
            other_post=np.full(n, np.nan),
            list_rank=np.zeros(n, dtype=np.int32),
            other_list_rank=np.zeros(n, dtype=np.int32),
            matched=np.zeros(n, dtype=np.bool_),
        )


class RunData:
    """A finished run's population, per-agent results and market model, loaded from its artifacts.

    The artifacts are the run's own, read from the database, unless `artifacts` gives them (by RunArtifact.Kind): a
    saved example run (nrmps.examples) is not in the database and brings the contents of its files.
    """

    def __init__(self, run: SimulationRun, artifacts: Mapping[str, bytes] | None = None):
        self.run = run
        self.params = run.get_params()
        artifact = run.artifact if artifacts is None else artifacts.get
        population_data = artifact(RunArtifact.Kind.POPULATION)
        if population_data is None:
            raise PopulationError("The run has no stored population.")
        self.population = population_from_npz(population_data)
        results = artifact(RunArtifact.Kind.PRE_INTERVIEW)
        self.applicant_results: SideResult | None = None
        self.program_results: SideResult | None = None
        if results is not None:
            self.applicant_results, self.program_results = results_from_npz(results)
        stages = artifact(RunArtifact.Kind.STAGES)
        self.stages: StageRecord | None = stages_from_npz(stages) if stages is not None else None

    def applicant_totals(self) -> dict[str, NDArray[Any]] | None:
        """Return per applicant: applications, signals, interviews, list length, matched program and its rank."""
        record = self.stages
        if record is None:
            return None
        n = self.population.n_applicants
        return {
            "applications": np.bincount(record.i, minlength=n),
            "signals": np.bincount(record.i[record.signal_tier >= 0], minlength=n),
            "interviews": np.bincount(record.i[record.accepted], minlength=n),
            "list_length": np.bincount(record.i[record.applicant_rank > 0], minlength=n),
            "match": record.match_program,
            "match_rank": record.match_applicant_rank.astype(np.int64),
        }

    def program_totals(self) -> dict[str, NDArray[Any]] | None:
        """Return per program: applications and signals received, invitations, interviews, list length and filled."""
        record = self.stages
        if record is None:
            return None
        m = self.population.n_programs
        return {
            "applications": np.bincount(record.j, minlength=m),
            "signals": np.bincount(record.j[record.signal_tier >= 0], minlength=m),
            "invitations": np.bincount(record.j[record.invite_wave > 0], minlength=m),
            "interviews": np.bincount(record.j[record.accepted], minlength=m),
            "list_length": np.bincount(record.j[record.program_rank > 0], minlength=m),
            "filled": record.filled.astype(np.int64),
        }

    def stage_rows(self, agent: int, *, applicant: bool) -> StageRows | None:
        """Return one agent's stage outcomes for every target (applications, or applications received)."""
        record = self.stages
        if record is None:
            return None
        n_targets = self.population.n_programs if applicant else self.population.n_applicants
        mine = np.flatnonzero((record.i if applicant else record.j) == agent)
        targets = (record.j if applicant else record.i)[mine].astype(np.int64)
        rows = StageRows.empty(n_targets)
        rows.applied[targets] = True
        rows.signal[targets] = record.signal_tier[mine]
        rows.wave[targets] = record.invite_wave[mine]
        rows.interviewed[targets] = record.accepted[mine]
        own_rank, other_rank = (
            (record.applicant_rank, record.program_rank) if applicant else (record.program_rank, record.applicant_rank)
        )
        rows.list_rank[targets] = own_rank[mine]
        rows.other_list_rank[targets] = other_rank[mine]
        held = mine[record.accepted[mine]]
        if held.size:
            i, j = record.i[held].astype(np.int64), record.j[held].astype(np.int64)
            _u, _u_star, u_post, _v, _v_star, v_post = pair_views(
                self.params, self.model, i, j, self.run.seed, self.run.replicate
            )
            where = j if applicant else i
            rows.post[where] = u_post if applicant else v_post
            rows.other_post[where] = v_post if applicant else u_post
        if applicant:
            matched = int(record.match_program[agent])
            if matched >= 0:
                rows.matched[matched] = True
        else:
            rows.matched[np.flatnonzero(record.match_program == agent)] = True
        return rows

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

    def application_rows(self, chunk: int = 50_000) -> Iterator[list[Any]]:
        """Yield one row per application (APPLICATION_COLUMNS): the decisions of every stage and both sides' views."""
        record = self.stages
        if record is None:
            return
        applicants, programs = self.population.applicants, self.population.programs
        tiers = [tier.name for tier in self.params.signals.tiers]
        portfolio = self.params.apps.strategy == "portfolio"
        model, seed, replicate = self.model, self.run.seed, self.run.replicate
        for start in range(0, record.i.shape[0], chunk):
            rows = np.arange(start, min(start + chunk, record.i.shape[0]))
            i, j = record.i[rows].astype(np.int64), record.j[rows].astype(np.int64)
            u = model.applicants.pair_utilities(i, j)
            u_hat = u + model.applicant_view.pair_error(i, j)
            v = model.programs.pair_utilities(j, i)
            v_hat = v + model.program_view.pair_error(j, i)
            u_star, u_post, v_star, v_post = (np.full(rows.shape[0], np.nan) for _ in range(4))
            held = np.flatnonzero(record.accepted[rows])
            if held.size:
                _u, u_star[held], u_post[held], _v, v_star[held], v_post[held] = pair_views(
                    self.params, model, i[held], j[held], seed, replicate
                )
            for k, pair in enumerate(rows.tolist()):
                applicant, program = int(i[k]), int(j[k])
                tier, wave = int(record.signal_tier[pair]), int(record.invite_wave[pair])
                yield [
                    applicants.name(applicant),
                    programs.name(program),
                    int(record.pre_rank[pair]),
                    CATEGORY_NAMES[int(record.category[pair])] if portfolio else "",
                    tiers[tier] if 0 <= tier < len(tiers) else "",
                    wave or "",
                    int(record.accepted[pair]),
                    _number(u[k]),
                    _number(u_hat[k]),
                    _number(u_star[k]),
                    _number(u_post[k]),
                    _number(v[k]),
                    _number(v_hat[k]),
                    _number(v_star[k]),
                    _number(v_post[k]),
                    int(record.applicant_rank[pair]) or "",
                    int(record.program_rank[pair]) or "",
                    int(record.match_program[applicant] == program),
                ]

    def match_rows(self) -> Iterator[list[Any]]:
        """Yield one row per applicant (MATCH_COLUMNS): the stages' totals and the match."""
        totals = self.applicant_totals()
        record = self.stages
        if totals is None or record is None:
            return
        applicants, programs = self.population.applicants, self.population.programs
        for i in range(applicants.size):
            matched = int(record.match_program[i])
            other = int(record.alternative[i]) if record.alternative is not None else None
            yield [
                applicants.name(i),
                applicants.group_names[applicants.group[i]],
                repr(float(applicants.strength[i])),
                int(totals["applications"][i]),
                int(totals["signals"][i]),
                int(totals["interviews"][i]),
                int(totals["list_length"][i]),
                programs.name(matched) if matched >= 0 else "",
                int(record.match_applicant_rank[i]) or "",
                int(record.match_program_rank[i]) or "",
                "" if other is None else programs.name(other) if other >= 0 else "unmatched",
            ]

    def program_result_rows(self) -> Iterator[list[Any]]:
        """Yield one row per program (PROGRAM_RESULT_COLUMNS): the stages' totals and the positions filled."""
        totals = self.program_totals()
        if totals is None:
            return
        programs = self.population.programs
        for j in range(programs.size):
            yield [
                programs.name(j),
                programs.tier_names[programs.tier[j]],
                repr(float(programs.quality[j])),
                int(programs.capacity[j]),
                int(totals["applications"][j]),
                int(totals["signals"][j]),
                int(totals["invitations"][j]),
                int(totals["interviews"][j]),
                int(totals["list_length"][j]),
                int(totals["filled"][j]),
            ]


def _number(value: float) -> str:
    """Return a float for a CSV cell: the exact repr, or blank for NaN."""
    return "" if np.isnan(value) else repr(float(value))


CATEGORY_NAMES = {TARGET: "target", REACH: "reach", SAFETY: "safety"}

APPLICATION_COLUMNS = [
    "applicant",
    "program",
    "applicant_pre_interview_rank",
    "category",
    "signal",
    "invitation_wave",
    "interviewed",
    "applicant_true_utility",
    "applicant_pre_interview_view",
    "applicant_realised_utility",
    "applicant_post_interview_view",
    "program_true_utility",
    "program_pre_interview_view",
    "program_realised_utility",
    "program_post_interview_view",
    "applicant_list_rank",
    "program_list_rank",
    "matched",
]

MATCH_COLUMNS = [
    "applicant",
    "group",
    "strength",
    "applications",
    "signals",
    "interviews",
    "list_length",
    "matched_program",
    "applicant_rank_of_match",
    "program_rank_of_applicant",
    "program_if_the_other_side_proposes",
]

PROGRAM_RESULT_COLUMNS = [
    "program",
    "tier",
    "quality",
    "positions",
    "applications",
    "signals",
    "invitations",
    "interviews",
    "list_length",
    "filled",
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
