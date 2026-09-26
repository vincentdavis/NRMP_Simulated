"""Database models: users, simulations with their draft parameters, uploaded populations and runs.

A simulation holds editable parameters (`nrmps.params`, schema v1). Starting a run freezes a copy of them with the
seed, the version stamps and the population the run uses; the run then stores what the engine produced: a record per
stage, the diagnostics and array artifacts. Pair-level values are recomputed from the population when a page needs
them (model 2.0 makes that exact), so no table grows with applicants x programs.
"""

import secrets
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Coalesce, Lower

from .params import SimulationParams, load_params


# Referenced by migrations 0002-0012 (the removed SimulationConfig); keep them importable.
def default_school_meta_preference() -> list[str]:
    """Return the legacy default applicant attributes that programs evaluate."""
    return ["board_scores", "research", "honors"]


def default_applicant_meta_preference() -> list[str]:
    """Return the legacy default program attributes that applicants evaluate."""
    return ["program_size", "reputation", "location"]


def new_seed() -> int:
    """Return a random seed that is easy to read and type (up to nine digits)."""
    return secrets.randbelow(10**9)


def default_params() -> dict[str, Any]:
    """Return the default parameters with a fresh seed, so runs repeat exactly until the seed is changed."""
    return SimulationParams().with_seed(new_seed()).to_json_data()


class User(AbstractUser):
    """Custom user model extending Django's AbstractUser (which provides username, password and email).

    Email addresses are unique ignoring case (empty addresses, from accounts created before email was required,
    are exempt) and verified through a signed link.
    """

    full_name = models.CharField(max_length=255, blank=True, default="")
    email_verified_at = models.DateTimeField(
        null=True, blank=True, help_text="When the current email address was confirmed (empty: not confirmed)."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("email"), condition=~models.Q(email=""), name="unique_user_email_ignoring_case"
            ),
        ]

    def __str__(self):
        return self.username

    @property
    def email_verified(self) -> bool:
        """Return True if the current email address has been confirmed."""
        return self.email_verified_at is not None


class SimulationQuerySet(models.QuerySet):
    """Queries for simulations."""

    def owned_by(self, user) -> SimulationQuerySet:
        """Return the simulations `user` owns (none for an anonymous user)."""
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(owner=user)

    def with_run_summary(self) -> SimulationQuerySet:
        """Annotate n_runs and the latest run's number and status (one subquery each, no N+1)."""
        latest = SimulationRun.objects.filter(simulation=models.OuterRef("pk")).order_by("-number")
        runs = (
            SimulationRun.objects.filter(simulation=models.OuterRef("pk"))
            .order_by()
            .values("simulation")
            .annotate(n=models.Count("*"))
            .values("n")
        )
        return self.annotate(
            n_runs=Coalesce(models.Subquery(runs), 0),
            latest_run_number=models.Subquery(latest.values("number")[:1]),
            latest_run_status=models.Subquery(latest.values("status")[:1]),
        )


class Simulation(models.Model):
    """A simulation: its owner, name, draft parameters, uploaded populations and runs."""

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="simulations")
    name = models.CharField(max_length=255, help_text="A short name for this experiment.")
    public = models.BooleanField(
        default=False,
        help_text="Planned: let others view this simulation read-only. Currently has no effect; only you can see it.",
    )
    description = models.TextField(default="", blank=True, help_text="Notes on what you are testing (optional).")
    params = models.JSONField(
        default=default_params, help_text="The draft parameters (schema v1 of nrmps.params); runs copy them."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SimulationQuerySet.as_manager()

    def __str__(self):
        return self.name

    def get_params(self) -> SimulationParams:
        """Return the validated draft parameters."""
        return load_params(self.params)

    def set_params(self, params: SimulationParams) -> None:
        """Replace the draft parameters (call save() afterwards)."""
        self.params = params.to_json_data()

    def lock(self) -> None:
        """Lock this simulation's row until the surrounding transaction ends.

        Call inside `transaction.atomic()`. Two requests that change the same simulation then run one after the
        other instead of interleaving (review finding CRIT-1). SQLite has no row locks and serialises writes instead.
        """
        Simulation.objects.select_for_update().only("id").get(pk=self.pk)

    def active_run(self) -> SimulationRun | None:
        """Return the queued or running run, if any (there is at most one)."""
        return self.runs.filter(status__in=SimulationRun.ACTIVE).first()

    def latest_run(self, *, succeeded: bool = False) -> SimulationRun | None:
        """Return the most recent run, or the most recent successful one."""
        runs = self.runs.filter(status=SimulationRun.Status.SUCCEEDED) if succeeded else self.runs.all()
        return runs.order_by("-number").first()

    def uploads_by_side(self) -> dict[str, PopulationUpload]:
        """Return the uploaded populations keyed by side ("applicants", "programs")."""
        return {upload.side: upload for upload in self.uploads.defer("data")}


class Side(models.TextChoices):
    """The two sides of the market."""

    APPLICANTS = "applicants", "Applicants"
    PROGRAMS = "programs", "Programs"


class PopulationUpload(models.Model):
    """A population uploaded as CSV for one side, used by the simulation's runs instead of a generated one."""

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="uploads")
    side = models.CharField(max_length=20, choices=Side.choices)
    filename = models.CharField(max_length=255, blank=True, default="")
    rows = models.PositiveIntegerField()
    data = models.BinaryField(help_text="The parsed file as npz (nrmps.population_csv).")
    digest = models.CharField(max_length=64, help_text="SHA-256 of `data`.")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["simulation", "side"], name="one_upload_per_side")]

    def __str__(self):
        return f"{self.get_side_display()} of {self.simulation_id}: {self.filename}"


class Stage(models.TextChoices):
    """Pipeline stages in order (model_spec.md; plan step 2.4). Only the first two are implemented."""

    POPULATION = "population", "Population"
    PRE_INTERVIEW = "pre_interview", "Pre-interview"
    APPLICATIONS = "applications", "Applications"
    SIGNALS = "signals", "Signals"
    INVITATIONS = "invitations", "Invitations"
    INTERVIEWS = "interviews", "Interviews"
    RANK_LISTS = "rank_lists", "Rank order lists"
    MATCH = "match", "Match"


IMPLEMENTED_STAGES = (Stage.POPULATION, Stage.PRE_INTERVIEW)


class SimulationRun(models.Model):
    """One execution of the pipeline: frozen parameters, seed, versions, population and results."""

    class Status(models.TextChoices):
        """Where the run is."""

        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Finished"
        FAILED = "failed", "Failed"

    ACTIVE = (Status.QUEUED, Status.RUNNING)

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="runs")
    number = models.PositiveIntegerField(help_text="1, 2, 3 ... within the simulation.")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True, help_text="Engine time, start to finish.")
    # What the run used.
    params = models.JSONField(help_text="The parameters, with the seed that was used.")
    params_hash = models.CharField(max_length=64)
    seed = models.BigIntegerField()
    seed_was_drawn = models.BooleanField(default=False, help_text="The draft had no seed, so one was drawn.")
    replicate = models.PositiveIntegerField(default=0)
    population_source = models.JSONField(default=dict, help_text='Per side: "generated" or the uploaded file name.')
    population_digest = models.CharField(max_length=64, blank=True, default="")
    fingerprints = models.JSONField(default=dict, help_text="Per stage: a hash of everything the stage depends on.")
    n_applicants = models.PositiveIntegerField(default=0)
    n_programs = models.PositiveIntegerField(default=0)
    n_positions = models.PositiveIntegerField(default=0)
    # Version stamps (model_spec.md §12.11).
    model_version = models.CharField(max_length=20)
    engine_version = models.CharField(max_length=20)
    schema_version = models.PositiveSmallIntegerField()
    app_version = models.CharField(max_length=20)
    git_sha = models.CharField(max_length=40, blank=True, default="")
    numpy_version = models.CharField(max_length=20)
    python_version = models.CharField(max_length=20)
    # Results and progress.
    metrics = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    progress_done = models.PositiveBigIntegerField(default=0)
    progress_total = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["simulation", "number"], name="unique_run_number"),
            models.UniqueConstraint(
                fields=["simulation"],
                condition=models.Q(status__in=["queued", "running"]),
                name="one_active_run_per_simulation",
            ),
        ]
        indexes = [models.Index(fields=["status", "created_at"], name="run_status_created")]

    def __str__(self):
        return f"{self.simulation} run {self.number}"

    @property
    def is_active(self) -> bool:
        """Return True while the run is queued or running."""
        return self.status in self.ACTIVE

    @property
    def n_pairs(self) -> int:
        """Return applicants x programs."""
        return self.n_applicants * self.n_programs

    @property
    def progress_percent(self) -> int:
        """Return the progress as a whole percentage."""
        if not self.progress_total:
            return 0
        return min(100, int(100 * self.progress_done / self.progress_total))

    def get_params(self) -> SimulationParams:
        """Return the frozen parameters."""
        return load_params(self.params)

    def stamps(self) -> dict[str, str | int]:
        """Return the version stamps."""
        return {
            "model_version": self.model_version,
            "engine_version": self.engine_version,
            "schema_version": self.schema_version,
            "app_version": self.app_version,
            "git_sha": self.git_sha,
            "numpy_version": self.numpy_version,
            "python_version": self.python_version,
        }

    def artifact(self, kind: str) -> bytes | None:
        """Return the bytes of one artifact, or None."""
        row = self.artifacts.filter(kind=kind).values_list("data", flat=True).first()
        return bytes(row) if row is not None else None


class StageRun(models.Model):
    """One stage of a run: when it ran, what it depended on and what it produced."""

    run = models.ForeignKey(SimulationRun, on_delete=models.CASCADE, related_name="stages")
    stage = models.CharField(max_length=20, choices=Stage.choices)
    status = models.CharField(max_length=20, choices=SimulationRun.Status.choices)
    fingerprint = models.CharField(max_length=64)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    counts = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "stage"], name="unique_stage_per_run")]

    def __str__(self):
        return f"{self.run} {self.get_stage_display()}"


class RunArtifact(models.Model):
    """Array results of a run, stored as npz bytes (nrmps.engine.persistence)."""

    class Kind(models.TextChoices):
        """What the artifact holds."""

        POPULATION = "population", "Population"
        PRE_INTERVIEW = "pre_interview", "Pre-interview results"

    run = models.ForeignKey(SimulationRun, on_delete=models.CASCADE, related_name="artifacts")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    data = models.BinaryField()
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "kind"], name="unique_artifact_kind_per_run")]

    def __str__(self):
        return f"{self.run} {self.kind}"
