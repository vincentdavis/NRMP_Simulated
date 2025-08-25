from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
    name = models.CharField(max_length=255)
    public = models.BooleanField(default=True)
    description = models.TextField(default="")
    iterations = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])
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
        - Returns the number of students created.
        """
        import random

        config = self.configs.order_by("-id").first()
        if config is None:
            # No configuration: nothing to create
            return 0

        # Remove existing population for a fresh generation
        self.students.all().delete()

        mean = config.applicants_score_mean
        std = max(float(config.applicant_score_stddev), 0.0)
        to_create = []
        for i in range(1, int(config.number_of_applicants) + 1):
            score = random.gauss(mean, std) if std > 0 else float(mean)
            to_create.append(Student(simulation=self, name=f"Student {i}", score=float(score)))

        Student.objects.bulk_create(to_create, batch_size=1000)
        return len(to_create)

    def create_schools(self) -> int:
        """Create the school population for this simulation using its latest SimulationConfig.

        Behavior:
        - Uses the most recent SimulationConfig linked to this Simulation (by id desc).
        - Clears existing schools for this simulation before creation.
        - Generates `number_of_schools` schools named "School {i}" with capacities and scores drawn from
          Gaussian distributions using the respective means and stddevs. Capacity is coerced to an int >= 0.
        - Returns the number of schools created.
        """
        import random

        config = self.configs.order_by("-id").first()
        if config is None:
            return 0

        self.schools.all().delete()

        score_mean = config.schools_score_mean
        score_std = max(float(config.schools_score_stddev), 0.0)
        cap_mean = config.school_capacity_mean
        cap_std = max(float(config.school_capacity_stddev), 0.0)

        to_create = []
        for i in range(1, int(config.number_of_schools) + 1):
            score = random.gauss(score_mean, score_std) if score_std > 0 else float(score_mean)
            capacity_raw = random.gauss(cap_mean, cap_std) if cap_std > 0 else float(cap_mean)
            capacity = int(round(capacity_raw))
            if capacity < 0:
                capacity = 0
            to_create.append(
                School(
                    simulation=self,
                    name=f"School {i}",
                    capacity=capacity,
                    score=float(score),
                )
            )

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

        Expected CSV format (with header): name,score
        File path convention: data/simulation_{self.id}_students.csv
        - Replaces existing students for this simulation.
        - Returns the number of students created. Returns 0 if the file does not exist.
        """
        import csv
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
                    score = float(row[1]) if len(row) > 1 and row[1] != "" else 0.0
                    to_create.append(Student(simulation=self, name=name, score=score))
            else:
                for row in reader:
                    name = (row.get(name_key) or "").strip() or None
                    score_val = row.get(score_key)
                    try:
                        score = float(score_val) if score_val not in (None, "") else 0.0
                    except ValueError:
                        score = 0.0
                    if not name:
                        name = f"Student {len(to_create) + 1}"
                    to_create.append(Student(simulation=self, name=name, score=score))

        if to_create:
            Student.objects.bulk_create(to_create, batch_size=1000)
        return len(to_create)

    def upload_schools(self) -> int:
        """Upload schools from a CSV file located in BASE_DIR/data.

        Expected CSV format (with header): name,capacity,score
        File path convention: data/simulation_{self.id}_schools.csv
        - Replaces existing schools for this simulation.
        - Returns the number of schools created. Returns 0 if the file does not exist.
        """
        import csv
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
                    if capacity < 0:
                        capacity = 0
                    to_create.append(School(simulation=self, name=name, capacity=capacity, score=score))
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
                    if capacity < 0:
                        capacity = 0
                    if not name:
                        name = f"School {len(to_create) + 1}"
                    to_create.append(School(simulation=self, name=name, capacity=capacity, score=score))

        if to_create:
            School.objects.bulk_create(to_create, batch_size=1000)
        return len(to_create)


class SimulationConfig(models.Model):
    """Simulation configuration model.

    This contains the configuration of the simulation
    """

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="configs")
    number_of_applicants = models.IntegerField()
    number_of_schools = models.IntegerField()

    # Applicant score configuration
    applicants_score_mean = models.FloatField(default=0)
    applicant_score_stddev = models.FloatField(default=25)
    applicants_interview_limit = models.FloatField(default=5)

    # School configuration
    schools_score_mean = models.FloatField(default=0)
    schools_score_stddev = models.FloatField(default=25)
    school_capacity_mean = models.FloatField(default=20)
    school_capacity_stddev = models.FloatField(default=10)
    school_interview_limit = models.FloatField(default=10)

    def __str__(self):
        return f"{self.simulation.name}-{self.id}"


class Student(models.Model):
    """Student model.

    This contains each student in a simulation. The student "population".
    """

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="students")
    name = models.CharField(max_length=255)
    score = models.FloatField()

    def __str__(self):
        return self.name


class School(models.Model):
    """School model.

    This contains each school in a simulation. The school "population".
    """

    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="schools")
    name = models.CharField(max_length=255)
    capacity = models.IntegerField()
    score = models.FloatField()

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
    status = models.CharField(max_length=50)
    students_rank_of_school = models.IntegerField(default=None)
    schools_rank_of_student = models.IntegerField(default=None)

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
    students_rank_of_school = models.IntegerField(default=None)
    schools_rank_of_student = models.IntegerField(default=None)

    class Meta:
        unique_together = ["student", "school"]

    def __str__(self):
        return f"Match: {self.student.name} - {self.school.name}"
