import functools
import math
import random

import numpy as np
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from scipy.stats import beta

from .exceptions import MissingConfigError
from .validators import validate_attribute_list


def default_school_meta_preference():
    return ["board_scores", "research", "honors"]


def default_applicant_meta_preference():
    return ["program_size", "reputation", "location"]


def get_beta_parameters(mean: float, desired_stddev: float) -> tuple[float, float]:
    """Convert mean and desired standard deviation to beta distribution parameters.

    For a beta distribution, if stddev is too large for the given mean,
    it will be automatically reduced to the maximum possible value.

    Returns:
        tuple: (alpha, beta) parameters for beta distribution
    """
    # Ensure mean is within valid range for beta distribution
    mean = max(0.001, min(0.999, mean))

    # Calculate maximum possible stddev for this mean
    max_stddev = np.sqrt(mean * (1 - mean))

    # If desired stddev is too large, reduce it
    if desired_stddev > max_stddev:
        desired_stddev = max_stddev * 0.9  # Use 90% of max to be safe

    # Calculate beta parameters from mean and variance
    variance = desired_stddev**2

    # For beta distribution: mean = a/(a+b), var = ab/((a+b)^2 * (a+b+1))
    # Solving: a = mean * ((mean*(1-mean)/variance) - 1)
    #         b = (1-mean) * ((mean*(1-mean)/variance) - 1)
    temp = (mean * (1 - mean) / variance) - 1

    if temp <= 0:  # Invalid parameters, fall back to low variance distribution
        alpha = mean * 10
        beta = (1 - mean) * 10
    else:
        alpha = mean * temp
        beta = (1 - mean) * temp

    # Ensure parameters are positive
    alpha = max(0.1, alpha)
    beta = max(0.1, beta)

    return alpha, beta


def generate_beta_score(mean: float, stddev: float) -> float:
    """Generate a score from beta distribution with given mean and stddev."""
    alpha, beta_param = get_beta_parameters(mean, stddev)
    return float(beta.rvs(alpha, beta_param))


SIMULATION_STAGES = [
    ("setup", "Setup"),
    ("populations", "Populations"),
    ("initialized", "Initialized"),
    ("pre_interview", "Pre-Interview"),
    ("invitations", "Invitations"),
    ("post_interview", "Post-Interview"),
    ("final_rankings", "Final Rankings"),
    ("matched", "Matched"),
]

STAGE_ORDER = [s[0] for s in SIMULATION_STAGES]


def _population_change(method):
    """Run a population method in one transaction that locks the simulation, then reset the pipeline stage."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with transaction.atomic():
            self.lock()
            result = method(self, *args, **kwargs)
            self.refresh_population_stage()
        return result

    return wrapper


class User(AbstractUser):
    """Custom user model extending Django's AbstractUser.
    Note: Django's AbstractUser already includes username, password, email fields
    """

    full_name = models.CharField(max_length=255, blank=True, null=True)
    disabled = models.BooleanField(default=False, null=True, blank=True)
    status = models.CharField(max_length=50, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username


class Simulation(models.Model):
    """Simulation model.

    This contains the very basic simulations setup and links to the others parts of a simulation

    method: create_students() -> builds the population of students
     method: create_schools() -> builds the population of schools
     method: upload_students() -> uploads students from a CSV file
     method: upload_schools() -> uploads schools from a CSV file
    """

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="simulations")
    name = models.CharField(max_length=255, help_text="A short name for this experiment.")
    public = models.BooleanField(
        default=False,
        help_text="Planned: let others view this simulation read-only. Currently has no effect; only you can see it.",
    )
    description = models.TextField(default="", blank=True, help_text="Notes on what you are testing (optional).")
    iterations = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text=(
            "Planned: number of independent repeats with different random seeds; results will be aggregated. "
            "Not used yet."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=SIMULATION_STAGES, default="setup")

    def __str__(self):
        return self.name

    def stage_index(self) -> int:
        """Return the zero-based index of the current status in STAGE_ORDER."""
        try:
            return STAGE_ORDER.index(self.status)
        except ValueError:
            return 0

    def lock(self) -> None:
        """Lock this simulation's row until the surrounding transaction ends.

        Call inside `transaction.atomic()`. Two requests that change the same simulation then run one after the
        other instead of interleaving (review finding CRIT-1). SQLite has no row locks and serialises writes instead.
        """
        Simulation.objects.select_for_update().only("id").get(pk=self.pk)

    def set_stage(self, stage: str) -> None:
        """Set the pipeline stage, forwards or backwards.

        Re-running a step replaces its results and invalidates every later stage, so the stage moves to exactly
        the step that ran, even if the simulation had got further before.
        """
        if stage not in STAGE_ORDER:
            raise ValueError(f"Unknown stage {stage!r}")
        if self.status != stage:
            self.status = stage
            self.save(update_fields=["status"])

    def refresh_population_stage(self) -> None:
        """Reset the stage after a population change.

        Replacing or deleting applicants or programs deletes every interview row (by cascade), so the pipeline goes
        back to "populations" when both populations exist, or to "setup" otherwise.
        """
        both = self.students.exists() and self.schools.exists()
        self.set_stage("populations" if both else "setup")

    def get_workflow_stages(self) -> list[dict]:
        """Build a list of stage dicts for template rendering.

        Each dict has keys: key, label, complete, active, locked.
        """
        current_idx = self.stage_index()
        stages = []
        for idx, (key, label) in enumerate(SIMULATION_STAGES):
            stages.append(
                {
                    "key": key,
                    "label": label,
                    "complete": idx < current_idx,
                    "active": idx == current_idx,
                    "locked": idx > current_idx,
                }
            )
        return stages

    @_population_change
    def create_students(self) -> int:
        """Create the student population for this simulation using its latest SimulationConfig.

        Behavior:
        - Uses the most recent SimulationConfig linked to this Simulation (by id desc).
        - Clears existing students for this simulation before creation.
        - Generates `number_of_applicants` students named "Student {i}" with scores drawn from a
          beta distribution using applicants_score_mean and applicant_score_stddev, ensuring scores stay between 0-1.
        - Uses applicant_meta_scores_stddev from config when generating score_meta values based on
          config.school_meta_preference: each meta gets beta-distributed scores with base_score as mean.
        - Also generates meta_preference weights per student using config.applicant_meta_preference and
          config.applicant_meta_preference_stddev, storing the stddev into meta_stddev_preference.
        - Raises MissingConfigError if the simulation has no configuration.
        - Returns the number of students created.
        """
        import random

        config = self.configs.order_by("-id").first()
        if config is None:
            raise MissingConfigError()

        # Remove existing population for a fresh generation
        self.students.all().delete()

        mean = config.applicant_score_mean
        std = max(float(config.applicant_score_stddev), 0.0)
        meta_std = max(float(getattr(config, "applicant_meta_scores_stddev", 0.0) or 0.0), 0.0)
        meta_keys = list(getattr(config, "school_meta_preference", []) or [])

        # Applicant preference generation settings
        pref_keys = list(getattr(config, "applicant_meta_preference", []) or [])
        pref_std = max(float(getattr(config, "applicant_meta_preference_stddev", 0.0) or 0.0), 0.0)

        to_create = []
        for i in range(1, int(config.number_of_applicants) + 1):
            # Use beta distribution to ensure scores stay between 0-1
            base_score = generate_beta_score(mean, std) if std > 0 else float(mean)
            score_meta = {}
            for key in meta_keys:
                try:
                    k = str(key)
                except Exception:
                    k = str(key)
                # Generate meta scores using beta distribution with base_score as mean
                meta_score = generate_beta_score(base_score, meta_std) if meta_std > 0 else base_score
                score_meta[k] = float(meta_score)

            # Generate student meta-preferences: weights between 0.01 and 2.0, normalized to sum = 1
            meta_preference = {}
            for key in pref_keys:
                try:
                    k2 = str(key)
                except Exception:
                    k2 = str(key)
                w = random.gauss(1.0, pref_std) if pref_std > 0 else 1.0
                # Clamp to range [0.01, 2.0]
                w = max(0.01, min(2.0, w))
                meta_preference[k2] = float(w)

            # Normalize weights to sum to 1
            if meta_preference:
                weight_sum = sum(meta_preference.values())
                if weight_sum > 0:
                    for k in meta_preference:
                        meta_preference[k] = meta_preference[k] / weight_sum

            to_create.append(
                Student(
                    simulation=self,
                    name=f"Student {i}",
                    score=float(base_score),
                    score_meta=score_meta,
                    meta_stddev_preference=pref_std,
                    meta_preference=meta_preference,
                )
            )

        if to_create:
            Student.objects.bulk_create(to_create, batch_size=1000)
        return len(to_create)

    @_population_change
    def create_schools(self) -> int:
        """Create the school population for this simulation using its latest SimulationConfig.

        Behavior:
        - Uses the most recent SimulationConfig linked to this Simulation (by id desc).
        - Clears existing schools for this simulation before creation.
        - Generates `number_of_schools` schools named "School {i}" with scores drawn from a
          beta distribution using school_score_mean and school_score_stddev, ensuring scores stay between 0-1.
          Capacities use Gaussian distribution. Capacity is coerced to an int >= 0.
        - Uses school_meta_scores_stddev from config when generating score_meta values based on
          config.applicant_meta_preference: each meta gets beta-distributed scores with base_score as mean.
        - Also generates meta_preference weights per school using config.school_meta_preference and
          config.school_meta_preference_stddev, storing the stddev into meta_stddev_preference.
        - Raises MissingConfigError if the simulation has no configuration.
        - Returns the number of schools created.
        """
        import random

        config = self.configs.order_by("-id").first()
        if config is None:
            raise MissingConfigError()

        self.schools.all().delete()

        score_mean = config.school_score_mean
        score_std = max(float(config.school_score_stddev), 0.0)
        cap_mean = config.school_capacity_mean
        cap_std = max(float(config.school_capacity_stddev), 0.0)
        meta_std = max(float(getattr(config, "school_meta_scores_stddev", 0.0) or 0.0), 0.0)
        meta_keys = list(getattr(config, "applicant_meta_preference", []) or [])

        # School preference generation settings
        pref_keys = list(getattr(config, "school_meta_preference", []) or [])
        pref_std = max(float(getattr(config, "school_meta_preference_stddev", 0.0) or 0.0), 0.0)

        to_create = []
        for i in range(1, int(config.number_of_schools) + 1):
            # Use beta distribution to ensure scores stay between 0-1
            base_score = generate_beta_score(score_mean, score_std) if score_std > 0 else float(score_mean)
            capacity_raw = random.gauss(cap_mean, cap_std) if cap_std > 0 else float(cap_mean)
            capacity = int(round(capacity_raw))
            if capacity < 0:
                capacity = 0
            score_meta = {}
            for key in meta_keys:
                try:
                    k = str(key)
                except Exception:
                    k = str(key)
                # Generate meta scores using beta distribution with base_score as mean
                meta_score = generate_beta_score(base_score, meta_std) if meta_std > 0 else base_score
                score_meta[k] = float(meta_score)

            # Generate school meta preferences: weights between 0.01 and 2.0, normalized to sum = 1
            meta_preference = {}
            for key in pref_keys:
                try:
                    k2 = str(key)
                except Exception:
                    k2 = str(key)
                w = random.gauss(1.0, pref_std) if pref_std > 0 else 1.0
                # Clamp to range [0.01, 2.0]
                w = max(0.01, min(2.0, w))
                meta_preference[k2] = float(w)

            # Normalize weights to sum to 1
            if meta_preference:
                weight_sum = sum(meta_preference.values())
                if weight_sum > 0:
                    for k in meta_preference:
                        meta_preference[k] = meta_preference[k] / weight_sum

            to_create.append(
                School(
                    simulation=self,
                    name=f"School {i}",
                    capacity=capacity,
                    score=float(base_score),
                    score_meta=score_meta,
                    meta_stddev_preference=pref_std,
                    meta_preference=meta_preference,
                )
            )

        if to_create:
            School.objects.bulk_create(to_create, batch_size=1000)
        return len(to_create)

    @_population_change
    def delete_students(self) -> int:
        """Delete the student population for this simulation."""
        self.students.all().delete()

    @_population_change
    def delete_schools(self) -> int:
        """Delete the school population for this simulation."""
        self.schools.all().delete()

    @_population_change
    def upload_students(self) -> int:
        """Upload students from a CSV file located in BASE_DIR/data.

        Expected CSV format (with header): name,score[,score_meta]
        - score_meta: JSON object string mapping meta names to values.
        File path convention: data/simulation_{self.id}_students.csv
        - Replaces existing students for this simulation.
        - Returns the number of students created. Returns 0 if the file does not exist.
        """
        import csv
        import json
        from pathlib import Path

        from django.conf import settings

        data_dir = Path(getattr(settings, "BASE_DIR", ".")) / "data"
        csv_path = data_dir / f"simulation_{self.id}_students.csv"
        if not csv_path.exists():
            return 0

        self.students.all().delete()

        to_create = []
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Minimal validation for expected headers
            field_map = {k.strip().lower(): k for k in reader.fieldnames or []}
            name_key = field_map.get("name")
            score_key = field_map.get("score")
            score_meta_key = field_map.get("score_meta")
            if not name_key or not score_key:
                # If headers missing, attempt to read as positional columns
                f.seek(0)
                raw_reader = csv.reader(f)
                # Skip header row if present but unknown names
                next(raw_reader, None)
                for idx, row in enumerate(raw_reader, start=1):
                    if not row:
                        continue
                    name = row[0].strip() if len(row) > 0 else f"Student {idx}"
                    try:
                        score = float(row[1]) if len(row) > 1 and row[1] != "" else 0.0
                    except ValueError:
                        score = 0.0
                    score_meta = {}
                    # If a third column exists, treat it as score_meta JSON and ignore any legacy meta_stddev column
                    if len(row) > 2 and row[2]:
                        try:
                            score_meta = json.loads(row[2])
                        except Exception:
                            score_meta = {}
                    to_create.append(
                        Student(
                            simulation=self,
                            name=name,
                            score=score,
                            score_meta=score_meta,
                        )
                    )
            else:
                for row in reader:
                    name = (row.get(name_key) or "").strip() or None
                    score_val = row.get(score_key)
                    try:
                        score = float(score_val) if score_val not in (None, "") else 0.0
                    except ValueError:
                        score = 0.0
                    score_meta_str = row.get(score_meta_key) if score_meta_key else None
                    score_meta = {}
                    if score_meta_str:
                        try:
                            score_meta = json.loads(score_meta_str)
                        except Exception:
                            score_meta = {}
                    if not name:
                        name = f"Student {len(to_create) + 1}"
                    to_create.append(
                        Student(
                            simulation=self,
                            name=name,
                            score=score,
                            score_meta=score_meta,
                        )
                    )

        if to_create:
            Student.objects.bulk_create(to_create, batch_size=1000)
        return len(to_create)

    @_population_change
    def upload_schools(self) -> int:
        """Upload schools from a CSV file located in BASE_DIR/data.

        Expected CSV format (with header): name,capacity,score[,score_meta]
        - score_meta: JSON object string mapping meta names to values.
        File path convention: data/simulation_{self.id}_schools.csv
        - Replaces existing schools for this simulation.
        - Returns the number of schools created. Returns 0 if the file does not exist.
        """
        import csv
        import json
        from pathlib import Path

        from django.conf import settings

        data_dir = Path(getattr(settings, "BASE_DIR", ".")) / "data"
        csv_path = data_dir / f"simulation_{self.id}_schools.csv"
        if not csv_path.exists():
            return 0

        self.schools.all().delete()

        to_create = []
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            field_map = {k.strip().lower(): k for k in reader.fieldnames or []}
            name_key = field_map.get("name")
            cap_key = field_map.get("capacity")
            score_key = field_map.get("score")
            score_meta_key = field_map.get("score_meta")
            if not name_key:
                # Fallback: positional
                f.seek(0)
                raw_reader = csv.reader(f)
                next(raw_reader, None)
                for idx, row in enumerate(raw_reader, start=1):
                    if not row:
                        continue
                    name = row[0].strip() if len(row) > 0 else f"School {idx}"
                    try:
                        capacity = int(float(row[1])) if len(row) > 1 and row[1] != "" else 0
                    except ValueError:
                        capacity = 0
                    try:
                        score = float(row[2]) if len(row) > 2 and row[2] != "" else 0.0
                    except ValueError:
                        score = 0.0
                    try:
                        meta_stddev = float(row[3]) if len(row) > 3 and row[3] != "" else 0.0
                    except (ValueError, TypeError):
                        meta_stddev = 0.0
                    score_meta = {}
                    if len(row) > 4 and row[4]:
                        try:
                            score_meta = json.loads(row[4])
                        except Exception:
                            score_meta = {}
                    if capacity < 0:
                        capacity = 0
                    to_create.append(
                        School(
                            simulation=self,
                            name=name,
                            capacity=capacity,
                            score=score,
                            score_meta=score_meta,
                        )
                    )
            else:
                for row in reader:
                    name = (row.get(name_key) or "").strip() or None
                    cap_val = row.get(cap_key) if cap_key else None
                    score_val = row.get(score_key) if score_key else None
                    try:
                        capacity = int(float(cap_val)) if cap_val not in (None, "") else 0
                    except ValueError:
                        capacity = 0
                    try:
                        score = float(score_val) if score_val not in (None, "") else 0.0
                    except ValueError:
                        score = 0.0
                    # Ignore legacy meta_stddev column if present; we no longer store it
                    pass
                    score_meta_str = row.get(score_meta_key) if score_meta_key else None
                    score_meta = {}
                    if score_meta_str:
                        try:
                            score_meta = json.loads(score_meta_str)
                        except Exception:
                            score_meta = {}
                    if capacity < 0:
                        capacity = 0
                    if not name:
                        name = f"School {len(to_create) + 1}"
                    to_create.append(
                        School(
                            simulation=self,
                            name=name,
                            capacity=capacity,
                            score=score,
                            score_meta=score_meta,
                        )
                    )

        if to_create:
            School.objects.bulk_create(to_create, batch_size=1000)
        return len(to_create)


class SimulationConfig(models.Model):
    """Simulation configuration model.

    Parameters for generating the applicant (student) and program (school) populations and for the pre-interview
    ratings. Scores and attribute scores live on a 0-1 scale and are drawn from Beta distributions, so a standard
    deviation must stay below the Beta limit sqrt(mean * (1 - mean)); `clean()` enforces that for the base scores.
    """

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="configs")
    number_of_applicants = models.IntegerField(
        default=200,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text="How many applicants (medical students) to generate.",
    )
    number_of_schools = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="How many residency programs to generate.",
    )
    # Applicant score configuration
    applicant_score_mean = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0.01), MaxValueValidator(0.99)],
        help_text="Average applicant base (overall strength) score on a 0-1 scale.",
    )
    applicant_score_stddev = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0), MaxValueValidator(0.45)],
        help_text="How spread out applicant base scores are (SD on the 0-1 scale).",
    )
    applicant_interview_limit = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Not used yet: the most interviews an applicant can accept and attend.",
    )
    # The program attributes that applicants evaluate: every program gets a score for each name, and every applicant
    # gets a preference weight for each name.
    applicant_meta_preference = models.JSONField(
        default=default_applicant_meta_preference,
        validators=[validate_attribute_list],
        help_text="Program attributes applicants care about, e.g. program_size, reputation, location.",
    )
    # SD of the raw preference weights each applicant gives the program attributes.
    applicant_meta_preference_stddev = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0), MaxValueValidator(1.0)],
        help_text="How much applicants disagree about which program attributes matter.",
    )
    # SD of each applicant's attribute scores around their base score.
    applicant_meta_scores_stddev = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0), MaxValueValidator(0.45)],
        help_text="How much an applicant's attribute scores vary around their base score.",
    )
    applicant_pre_interview_rating_error = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0), MaxValueValidator(0.99)],
        help_text="How noisy applicants' view of programs is before interviewing (0 = perfect information).",
    )
    applicant_post_interview_rating_error = models.FloatField(
        default=0.02,
        validators=[MinValueValidator(0), MaxValueValidator(0.99)],
        help_text="Not used yet: how noisy applicants' view of programs is after interviewing.",
    )

    # School configuration
    school_score_mean = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.01), MaxValueValidator(0.99)],
        help_text="Average program base (overall quality) score on a 0-1 scale.",
    )
    school_score_stddev = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0), MaxValueValidator(0.45)],
        help_text="How spread out program base scores are (SD on the 0-1 scale).",
    )
    school_capacity_mean = models.FloatField(
        default=20,
        validators=[MinValueValidator(1)],
        help_text="Average number of residency positions per program.",
    )
    school_capacity_stddev = models.FloatField(
        default=4,
        validators=[MinValueValidator(0)],
        help_text="How much program sizes vary (at most half the mean is recommended).",
    )
    school_interview_limit = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0), MaxValueValidator(0.99)],
        help_text="Not used yet: Phase 2 replaces it with interviews per position.",
    )
    # The applicant attributes that programs evaluate: every applicant gets a score for each name, and every program
    # gets a preference weight for each name.
    school_meta_preference = models.JSONField(
        default=default_school_meta_preference,
        validators=[validate_attribute_list],
        help_text="Applicant attributes programs care about, e.g. board_scores, research, honors.",
    )
    # SD of the raw preference weights each program gives the applicant attributes.
    school_meta_preference_stddev = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0), MaxValueValidator(1.0)],
        help_text="How much programs disagree about which applicant attributes matter.",
    )
    # SD of each program's attribute scores around its base score.
    school_meta_scores_stddev = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0), MaxValueValidator(0.45)],
        help_text="How much a program's attribute scores vary around its base score.",
    )
    school_pre_interview_rating_error = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0), MaxValueValidator(0.99)],
        help_text="How noisy programs' view of applicants is from the application alone (0 = perfect information).",
    )
    school_post_interview_rating_error = models.FloatField(
        default=0.02,
        validators=[MinValueValidator(0), MaxValueValidator(0.99)],
        help_text="Not used yet: how noisy programs' view of applicants is after interviewing.",
    )

    def clean(self):
        """Reject base-score standard deviations that no Beta distribution with the requested mean can have.

        A Beta distribution with mean m has a standard deviation below sqrt(m * (1 - m)). Larger requests used to be
        silently cut, which produced U-shaped populations with a shifted mean.
        """
        errors = {}
        for side, label in (("applicant", "applicant"), ("school", "program")):
            mean = getattr(self, f"{side}_score_mean")
            stddev = getattr(self, f"{side}_score_stddev")
            if mean is None or stddev is None or not 0 < mean < 1:
                continue
            limit = math.sqrt(mean * (1 - mean))
            if stddev >= limit:
                errors[f"{side}_score_stddev"] = ValidationError(
                    "With a %(label)s score mean of %(mean)s the standard deviation must be below %(limit)s.",
                    code="beta_infeasible",
                    params={"label": label, "mean": f"{mean:g}", "limit": f"{limit:.3f}"},
                )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.simulation.name}-{self.id}"


def generate_meta_scores(self, score: float, meta_scores: list[str], meta_stddev: float) -> dict[str:float]:
    """Generates meta-scores for each student and school."""
    for meta in meta_scores:
        self.score_meta[meta] = score + random.gauss(0, meta_stddev)


# Example: This function will be hidden from documentation
generate_meta_scores.__doc_exclude__ = True


class Student(models.Model):
    """Student model.

    This contains each student in a simulation. The student "population".
    """

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="students")
    name = models.CharField(max_length=255, help_text="Applicant name.")
    score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(1.0)],
        help_text="Applicant's base (true overall) strength, 0-1; centre of their attribute scores.",
    )
    meta_stddev = models.FloatField(
        default=0.0, help_text="Standard deviation of the score."
    )  # This will define how close each score is to the base "score"
    score_meta = models.JSONField(
        default=dict,
        help_text=(
            "Applicant attribute scores (0-1) keyed by the attributes programs value, "
            'e.g. {"board_scores": 0.72, "research": 0.55, "honors": 0.61}.'
        ),
    )
    meta_stddev_preference = models.FloatField(
        default=0.0, help_text="SD used when this applicant's preference weights were drawn (copied from config)."
    )
    meta_preference = models.JSONField(
        default=dict,
        help_text=(
            "Applicant preference weights (sum to 1) keyed by the program attributes applicants value, "
            'e.g. {"program_size": 0.31, "reputation": 0.45, "location": 0.24}.'
        ),
    )

    def __str__(self):
        return self.name


class School(models.Model):
    """School model.

    This contains each school in a simulation. The school "population".
    """

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="schools")
    name = models.CharField(max_length=255, help_text="Program name.")
    capacity = models.IntegerField(help_text="Number of positions the program can fill (>= 0).")
    score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(1.0)],
        help_text="Program's base (true overall) quality, 0-1; centre of its attribute scores.",
    )
    meta_stddev = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(99)],
        default=1.0,
        help_text="Standard deviation of the score.",
    )  # This will define how close each score is to the base "score"
    score_meta = models.JSONField(
        default=dict,
        help_text=(
            "Program attribute scores (0-1) keyed by the attributes applicants value, "
            'e.g. {"program_size": 0.4, "reputation": 0.8, "location": 0.6}.'
        ),
    )
    meta_stddev_preference = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(99)],
        default=1.0,
        help_text="SD used when this program's preference weights were drawn (copied from config).",
    )
    meta_preference = models.JSONField(
        default=dict,
        help_text=(
            "Program preference weights (sum to 1) keyed by the applicant attributes programs value, "
            'e.g. {"board_scores": 0.5, "research": 0.3, "honors": 0.2}.'
        ),
    )

    def __str__(self):
        return self.name


class Interview(models.Model):
    """Interview model.

    This contains the interview step data for the simulation.
    It records the interview status between each student and school in the simulation.
    This includes the student's interview rank of the school and the school's interview rank of the student
    """

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="interviews")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="interviews")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="interviews")
    # Logic flags
    status = models.CharField(
        max_length=50,
        default="initialized",
        help_text="Stage reached for this pair (currently always initialized).",
    )

    # Student steps
    student_applied = models.BooleanField(default=False, help_text="True if the applicant applied to this program.")
    student_signal = models.IntegerField(
        default=0, help_text="Preference signal the applicant sent this program (0 = none). Not used yet."
    )
    student_accepted = models.BooleanField(
        default=False,
        help_text="True if the applicant accepted this program's interview invitation.",
    )
    student_true_score_of_school = models.FloatField(
        null=True,
        blank=True,
        help_text="Applicant's noise-free utility for this program (sum of weight x program attribute).",
    )

    # Schools Steps
    school_invited = models.BooleanField(
        default=False,
        help_text="True if the program invited this applicant to interview (requires an application).",
    )
    # Properties of the interview step
    ## Pre interview Observed score.
    student_pre_observed_score_of_school = models.FloatField(
        null=True, blank=True, help_text="Applicant's pre-interview (noisy) rating of this program."
    )
    school_pre_observed_score_of_student = models.FloatField(
        null=True, blank=True, help_text="Program's pre-interview (noisy) rating of this applicant."
    )
    school_true_score_of_student = models.FloatField(
        null=True,
        blank=True,
        help_text="Program's noise-free utility for this applicant (sum of weight x applicant attribute).",
    )

    ## Pre interview rank.
    students_pre_rank_of_school = models.IntegerField(
        null=True,
        blank=True,
        help_text="Where this program falls in the applicant's pre-interview ordering (1 = favourite).",
    )
    schools_pre_rank_of_student = models.IntegerField(
        null=True,
        blank=True,
        help_text="Where this applicant falls in the program's pre-interview ordering (1 = top applicant).",
    )

    ## Post interview Observed score.
    student_post_observed_score_of_school = models.FloatField(
        null=True, blank=True, help_text="Applicant's post-interview rating of this program."
    )
    school_post_observed_score_of_student = models.FloatField(
        null=True, blank=True, help_text="Program's post-interview rating of this applicant."
    )

    ## Post interview rank.
    students_post_rank_of_school = models.IntegerField(
        null=True, blank=True, help_text="Where this program falls in the applicant's post-interview ordering."
    )
    schools_post_rank_of_student = models.IntegerField(
        null=True, blank=True, help_text="Where this applicant falls in the program's post-interview ordering."
    )

    class Meta:
        unique_together = ["student", "school"]

    def __str__(self):
        return f"{self.student.name} - {self.school.name}"


class Match(models.Model):
    """Match model.

    This contains the match step data for the simulation.
    It records the match status between each student and school in the simulation
    This includes the student's match rank of the school and the school's match rank of the student
    """

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="matches")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="matches")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="matches")
    students_rank_of_school = models.IntegerField(null=True, blank=True)
    schools_rank_of_student = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ["student", "school"]

    def __str__(self):
        return f"Match: {self.student.name} - {self.school.name}"
