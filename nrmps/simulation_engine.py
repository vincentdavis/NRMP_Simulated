from nrmps.models import Interview, Simulation


def _score(meta_scores: dict[str:float], meta_preferances: dict[str:float], rating_error) -> float:
    """Compute the score for a student based on the meta-scores and the score.
    Calculating:
    - sum(meta_score * meta_preference)*rating_error.
    """
    return sum(meta_scores[meta] * meta_preferances[meta] for meta in meta_preferances) * rating_error


def initialize_interview(simulation: Simulation):
    """Initialize the interview objects for each student and school of a simulation.

    Recreates the full cross-product of Student x School for this simulation.
    """
    # Remove existing interviews for a clean re-init
    Interview.objects.filter(simulation=simulation).delete()
    to_create = []
    students = list(simulation.students.all())
    schools = list(simulation.schools.all())
    for student in students:
        for school in schools:
            to_create.append(Interview(simulation=simulation, student=student, school=school, status="initialized"))
    if to_create:
        Interview.objects.bulk_create(to_create, batch_size=1000)


def students_rate_schools_pre_interview(simulation: Simulation):
    """Students choose which schools they would like to apply to.

    Steps:
    1. Computes the students rating of each school.

    Details:
    - Compute each student's pre-interview observed score of each school.
      score = sum_over_meta(school.score_meta[m] * student.meta_preference[m]) * rating_error
    """
    # Use the latest config to get applicant pre-interview rating error
    cfg = simulation.configs.order_by("-id").first()
    rating_error = float(getattr(cfg, "applicant_pre_interview_rating_error", 1.0) or 1.0)

    from .models import Interview as InterviewModel  # avoid confusion with local name

    qs = InterviewModel.objects.select_related("student", "school").filter(simulation=simulation)
    for inter in qs:
        try:
            val = _score(inter.school.score_meta or {}, inter.student.meta_preference or {}, rating_error)
        except Exception:
            raise Exception(f"Error computing pre-interview score for {inter}") from None
            # val = None
        inter.student_pre_observed_score_of_school = val
        inter.save(update_fields=["student_pre_observed_score_of_school"])


def schools_rate_students(self):
    """Schools invite applicants to their interviews.

    Steps:
    1. Computes the schools rating of each student.
    2. Choose which students to interview.
        a. Rank the students that applied.
        b. invite the top
    """
    pass


def interview(self):
    """Students and schools interview each other.
    Students and Schools update their ratings after the interview.
    """


def students_rank():
    """Each student, using the post-interview rating, chooses which schools to rank and ranks them by rating.
    1 is the highest rank
    """
    pass


def schools_rank():
    """Each school, using the post-interview rating, chooses which students to rank and ranks them by rating."""
    pass


def match():
    """Run the NRMP match algorithm."""
    pass
