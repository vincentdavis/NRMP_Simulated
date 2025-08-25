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
    name = models.CharField(max_length=255)
    iterations = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default="pending")

    def __str__(self):
        return self.name


class SimulationConfig(models.Model):
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="configs")
    name = models.CharField(max_length=255)
    description = models.TextField()
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
        return f"{self.name} - {self.simulation.name}"


class Student(models.Model):
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="students")
    name = models.CharField(max_length=255)
    score = models.FloatField()

    def __str__(self):
        return self.name


class School(models.Model):
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="schools")
    name = models.CharField(max_length=255)
    capacity = models.IntegerField()
    score = models.FloatField()

    def __str__(self):
        return self.name


class Interview(models.Model):
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="interviews")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="interviews")

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="interviews")
    status = models.CharField(max_length=50)

    class Meta:
        unique_together = ["student", "school"]

    def __str__(self):
        return f"{self.student.name} - {self.school.name}"


class Match(models.Model):
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name="matches")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="matches")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="matches")

    class Meta:
        unique_together = ["student", "school"]

    def __str__(self):
        return f"Match: {self.student.name} - {self.school.name}"
