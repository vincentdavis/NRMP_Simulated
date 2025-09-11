import random

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def default_school_meta_preference():
    return ["board_scores", "research", "honors"]


def default_applicant_meta_preference():
    return ["program_size", "reputation", "location"]


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

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="simulations"
    )
    name = models.CharField(max_length=255)
    public = models.BooleanField(default=True)
    description = models.TextField(default="")
    iterations = models.IntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default="pending")

    def __str__(self):
        return self.name

    def create_students(self) -> int:
        """Create the student population for this simulation using its latest SimulationConfig.

        Behavior:
        - Uses the most recent SimulationConfig linked to this Simulation (by id desc).
        - Clears existing students for this simulation before creation.
        - Generates `number_of_applicants` students named "Student {i}" with scores drawn from a
          Gaussian distribution using applicants_score_mean and applicant_score_stddev.
        - Uses applicant_meta_scores_stddev from config when generating score_meta values based on
          config.school_meta_preference: each meta gets base score plus N(0, applicant_meta_scores_stddev).
        - Also generates meta_preference weights per student using config.applicant_meta_preference and
          config.applicant_meta_preference_stddev, storing the stddev into meta_stddev_preference.
        - Returns the number of students created.
        """
        import random

        config = self.configs.order_by("-id").first()
        if config is None:
            # No configuration: nothing to create
            return 0

        # Remove existing population for a fresh generation
        self.students.all().delete()

        mean = config.applicant_score_mean
        std = max(float(config.applicant_score_stddev), 0.0)
        meta_std = max(
            float(getattr(config, "applicant_meta_scores_stddev", 0.0) or 0.0), 0.0
        )
        meta_keys = list(getattr(config, "school_meta_preference", []) or [])

        # Applicant preference generation settings
        pref_keys = list(getattr(config, "applicant_meta_preference", []) or [])
        pref_std = max(
            float(getattr(config, "applicant_meta_preference_stddev", 0.0) or 0.0), 0.0
        )

        to_create = []
        for i in range(1, int(config.number_of_applicants) + 1):
            base_score = random.gauss(mean, std) if std > 0 else float(mean)
            score_meta = {}
            for key in meta_keys:
                try:
                    k = str(key)
                except Exception:
                    k = str(key)
                delta = random.gauss(0, meta_std) if meta_std > 0 else 0.0
                score_meta[k] = float(base_score + delta)

            # Generate student meta preferences: weights between 0.01 and 2.0, normalized to sum = 1
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

    def create_schools(self) -> int:
        """Create the school population for this simulation using its latest SimulationConfig.

        Behavior:
        - Uses the most recent SimulationConfig linked to this Simulation (by id desc).
        - Clears existing schools for this simulation before creation.
        - Generates `number_of_schools` schools named "School {i}" with capacities and scores drawn from
          Gaussian distributions using the respective means and stddevs. Capacity is coerced to an int >= 0.
        - Uses school_meta_scores_stddev from config when generating score_meta values based on
          config.applicant_meta_preference: each meta gets base score plus N(0, school_meta_scores_stddev).
        - Also generates meta_preference weights per school using config.school_meta_preference and
          config.school_meta_preference_stddev, storing the stddev into meta_stddev_preference.
        - Returns the number of schools created.
        """
        import random

        config = self.configs.order_by("-id").first()
        if config is None:
            return 0

        self.schools.all().delete()

        score_mean = config.school_score_mean
        score_std = max(float(config.school_score_stddev), 0.0)
        cap_mean = config.school_capacity_mean
        cap_std = max(float(config.school_capacity_stddev), 0.0)
        meta_std = max(
            float(getattr(config, "school_meta_scores_stddev", 0.0) or 0.0), 0.0
        )
        meta_keys = list(getattr(config, "applicant_meta_preference", []) or [])

        # School preference generation settings
        pref_keys = list(getattr(config, "school_meta_preference", []) or [])
        pref_std = max(
            float(getattr(config, "school_meta_preference_stddev", 0.0) or 0.0), 0.0
        )

        to_create = []
        for i in range(1, int(config.number_of_schools) + 1):
            base_score = (
                random.gauss(score_mean, score_std)
                if score_std > 0
                else float(score_mean)
            )
            capacity_raw = (
                random.gauss(cap_mean, cap_std) if cap_std > 0 else float(cap_mean)
            )
            capacity = int(round(capacity_raw))
            if capacity < 0:
                capacity = 0
            score_meta = {}
            for key in meta_keys:
                try:
                    k = str(key)
                except Exception:
                    k = str(key)
                delta = random.gauss(0, meta_std) if meta_std > 0 else 0.0
                score_meta[k] = float(base_score + delta)

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

    def delete_students(self) -> int:
        """Delete the student population for this simulation."""
        self.students.all().delete()

    def delete_schools(self) -> int:
        """Delete the school population for this simulation."""
        self.schools.all().delete()

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
                        capacity = (
                            int(float(row[1])) if len(row) > 1 and row[1] != "" else 0
                        )
                    except ValueError:
                        capacity = 0
                    try:
                        score = float(row[2]) if len(row) > 2 and row[2] != "" else 0.0
                    except ValueError:
                        score = 0.0
                    try:
                        meta_stddev = (
                            float(row[3]) if len(row) > 3 and row[3] != "" else 0.0
                        )
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
                        capacity = (
                            int(float(cap_val)) if cap_val not in (None, "") else 0
                        )
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

    This contains the configuration of the simulation
    """

    simulation = models.ForeignKey(
        Simulation, on_delete=models.CASCADE, related_name="configs"
    )
    number_of_applicants = models.IntegerField(
        default=200,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text="Total number of applicants to generate.",
    )
    number_of_schools = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Total number of schools to generate.",
    )
    # Applicant score configuration
    applicant_score_mean = models.FloatField(
        default=0,
        validators=[MinValueValidator(-1000), MaxValueValidator(1000)],
        help_text="Mean of the applicants' base scores.",
    )
    applicant_score_stddev = models.FloatField(
        default=25,
        validators=[MinValueValidator(0)],
        help_text="Std. dev. of the applicants' base scores (>= 0).",
    )
    applicant_interview_limit = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0)],
        help_text="Max number of interviews each applicant can attend.",
    )
    applicant_meta_preference = models.JSONField(
        default=default_applicant_meta_preference,
        help_text="List of applicant preference meta fields (e.g., program_size, prestige).",
    )  # This is the list of meta-fields that are used to by applicants to rank school. "The applicants' preferences".
    applicant_meta_preference_stddev = models.FloatField(
        validators=[MinValueValidator(0)],
        default=3,
        help_text="Std. dev. of meta preference scores (>= 0).",
    )  # This is the stddev of the meta-preferences "weights" each student gives to preferacnes.
    applicant_meta_scores_stddev = models.FloatField(
        default=10,
        validators=[MinValueValidator(0)],
        help_text="Std. dev. of meta scores per applicant (>= 0).",
    )  # This is the stddev of the meta-scores for each applicant.
    applicant_pre_interview_rating_error = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0)],
        help_text="Pre-interview rating error stddev",
    )  # The mean error is 0, this calculates the stdsdev used to computer the students error
    applicant_post_interview_rating_error = models.FloatField(
        default=0.02,
        validators=[MinValueValidator(0)],
        help_text="Pre-interview rating error stddev",
    )  # The mean error is 0, this calculates the stdsdev used to computer the students error

    # School configuration
    school_score_mean = models.FloatField(
        default=0,
        validators=[MinValueValidator(-1000), MaxValueValidator(1000)],
        help_text="Mean of the schools' base scores.",
    )
    school_score_stddev = models.FloatField(
        default=25,
        validators=[MinValueValidator(0)],
        help_text="Std. dev. of the schools' base scores (>= 0).",
    )
    school_capacity_mean = models.FloatField(
        default=20, help_text="Mean capacity per school."
    )
    school_capacity_stddev = models.FloatField(
        default=10,
        validators=[MinValueValidator(0)],
        help_text="Std. dev. of capacity per school (>= 0).",
    )
    school_interview_limit = models.FloatField(
        default=10,
        validators=[MinValueValidator(0)],
        help_text="Max number of interviews each school can conduct Inpercent of capacity.",
    )
    school_meta_preference = models.JSONField(
        default=default_school_meta_preference,
        help_text="List of school preference meta fields (e.g., board_scores, research).",
    )  # This is the list of meta-fields that are used by schools to rank a student. "The schools preferances".
    school_meta_preference_stddev = models.FloatField(
        default=3,
        validators=[MinValueValidator(0)],
    )  # This is the stddev of the meta-preferences "weights" each schools gives to preferences.
    school_meta_scores_stddev = models.FloatField(
        default=10,
        validators=[MinValueValidator(0)],
        help_text="Std. dev. of meta scores per school (>= 0).",
    )  # This is the stddev of the meta-scores for each school.
    school_pre_interview_rating_error = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0)],
        help_text="The stddev scoreing error used to calculate the observed score for each student",
    )
    school_post_interview_rating_error = models.FloatField(
        default=0.02,
        validators=[MinValueValidator(0)],
        help_text="The stddev scoreing error used to calculate the observed score for each student",
    )

    def __str__(self):
        return f"{self.simulation.name}-{self.id}"


def generate_meta_scores(
    self, score: float, meta_scores: list[str], meta_stddev: float
) -> dict[str:float]:
    """Generates meta-scores for each student and school."""
    for meta in meta_scores:
        self.score_meta[meta] = score + random.gauss(0, meta_stddev)


class Student(models.Model):
    """Student model.

    This contains each student in a simulation. The student "population".
    """

    simulation = models.ForeignKey(
        Simulation, on_delete=models.CASCADE, related_name="students"
    )
    name = models.CharField(max_length=255, help_text="Name of the student.")
    score = models.FloatField(
        help_text="Score of the student."
    )  # This sets the mean for the score meta
    meta_stddev = models.FloatField(
        default=0.0, help_text="Standard deviation of the score."
    )  # This will define how close each score is to the base "score"
    score_meta = models.JSONField(
        default=dict,
        help_text='Meta score names and value {"USMLE Setp 2":5, "Grades": 10} for the score.',
    )
    meta_stddev_preference = models.FloatField(
        default=0.0, help_text="Standard deviation of the preference."
    )  # This is the stddev of the meta-preferences "weights" this student applies to preferences.
    meta_preference = models.JSONField(
        default=dict,
        help_text='Meta score names and value {"School size":5, "Reputation": 10} for the preference.',
    )

    def __str__(self):
        return self.name


class School(models.Model):
    """School model.

    This contains each school in a simulation. The school "population".
    """

    simulation = models.ForeignKey(
        Simulation, on_delete=models.CASCADE, related_name="schools"
    )
    name = models.CharField(max_length=255, help_text="Name of the school.")
    capacity = models.IntegerField(help_text="Capacity of the school.")
    score = models.FloatField(
        help_text="Score of the school."
    )  # This sets the mean for the score meta
    meta_stddev = models.FloatField(
        default=0.0, help_text="Standard deviation of the score."
    )  # This will define how close each score is to the base "score"
    score_meta = models.JSONField(
        default=dict,
        help_text='Meta score names and value {"Research":5, "Reputation": 10} for the score.',
    )
    meta_stddev_preference = models.FloatField(
        default=0.0, help_text="Standard deviation of the preference."
    )  # This is the stddev of the meta-preferences "weights" this school applies to preferences.
    meta_preference = models.JSONField(
        default=dict,
        help_text='Meta score names and value {"USMLE Setp 2":5, "Grades": 10} for the preference.',
    )

    def __str__(self):
        return self.name


class Interview(models.Model):
    """Interview model.

    This contains the interview step data for the simulation.
    It records the interview status between each student and school in the simulation.
    This includes the student's interview rank of the school and the school's interview rank of the student
    """

    simulation = models.ForeignKey(
        Simulation, on_delete=models.CASCADE, related_name="interviews"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="interviews"
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="interviews"
    )
    # Logic flags
    status = models.CharField(max_length=50, default="initialized")

    # Student steps
    student_applied = models.BooleanField(
        default=False, help_text="Whether the student has been applied to the school."
    )
    student_signal = models.IntegerField(
        default=0, help_text="Signal value from the student to the school"
    )
    student_accepted = models.BooleanField(
        default=False,
        help_text="Whether the student has been accepted to the school invitation to interview.",
    )
    student_true_score_of_school = models.FloatField(
        null=True, blank=True, help_text="True score of school with respect to student"
    )

    # Schools Steps
    school_invited = models.BooleanField(
        default=False,
        help_text="Whether the school has been invited to the interview. Must have applied to school first",
    )
    # Properties of the interview step
    ## Pre interview Observed score.
    student_pre_observed_score_of_school = models.FloatField(
        null=True, blank=True, help_text='Pre interview "total" score of student'
    )
    school_pre_observed_score_of_student = models.FloatField(
        null=True, blank=True, help_text='Pre interview "total" score of school'
    )
    school_true_score_of_student = models.FloatField(
        null=True, blank=True, help_text="True score of student with respect to school"
    )

    ## Pre interview rank.
    students_pre_rank_of_school = models.IntegerField(
        null=True, blank=True, help_text="Pre interview rank of student"
    )
    schools_pre_rank_of_student = models.IntegerField(
        null=True, blank=True, help_text="Pre interview rank of school"
    )

    ## Post interview Observed score.
    student_post_observed_score_of_school = models.FloatField(
        null=True, blank=True, help_text='Post interview "total score" of student'
    )
    school_post_observed_score_of_student = models.FloatField(
        null=True, blank=True, help_text='Post interview "total" score of school'
    )

    ## Post interview rank.
    students_post_rank_of_school = models.IntegerField(
        null=True, blank=True, help_text="Post interview rank of student"
    )
    schools_post_rank_of_student = models.IntegerField(
        null=True, blank=True, help_text="Post interview rank of school"
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

    simulation = models.ForeignKey(
        Simulation, on_delete=models.CASCADE, related_name="matches"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="matches"
    )
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="matches")
    students_rank_of_school = models.IntegerField(null=True, blank=True)
    schools_rank_of_student = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ["student", "school"]

    def __str__(self):
        return f"Match: {self.student.name} - {self.school.name}"
