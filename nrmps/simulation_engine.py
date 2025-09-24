from nrmps.models import Interview, Simulation


def _score(meta_scores: dict[str, float], meta_preferances: dict[str, float], rating_error) -> float:
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
            to_create.append(
                Interview(
                    simulation=simulation,
                    student=student,
                    school=school,
                    status="initialized",
                )
            )

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
    # Use the latest config to get the applicant pre-interview rating error
    cfg = simulation.configs.order_by("-id").first()
    rating_error = float(getattr(cfg, "applicant_pre_interview_rating_error", 1.0) or 1.0)

    from .models import Interview as InterviewModel  # avoid confusion with local name

    qs = InterviewModel.objects.select_related("student", "school").filter(simulation=simulation)
    for inter in qs:
        try:
            val = _score(
                inter.school.score_meta or {},
                inter.student.meta_preference or {},
                rating_error,
            )
        except Exception:
            raise Exception(f"Error computing pre-interview score for {inter}") from None
            # val = None
        inter.student_pre_observed_score_of_school = val
        inter.save(update_fields=["student_pre_observed_score_of_school"])


def schools_rate_students_pre_interview(simulation: Simulation):
    """Schools rate students for pre-interview evaluation.

    Steps:
    1. Computes the schools' rating of each student.

    Details:
    - Compute each school's pre-interview observed score of each student.
      score = sum_over_meta(student.score_meta[m] * school.meta_preference[m]) * rating_error
    """
    # Use the latest config to get the school pre-interview rating error
    cfg = simulation.configs.order_by("-id").first()
    rating_error = float(getattr(cfg, "school_pre_interview_rating_error", 1.0) or 1.0)

    from .models import Interview as InterviewModel  # avoid confusion with local name

    qs = InterviewModel.objects.select_related("student", "school").filter(simulation=simulation)
    for inter in qs:
        try:
            val = _score(
                inter.student.score_meta or {},
                inter.school.meta_preference or {},
                rating_error,
            )
        except Exception:
            raise Exception(f"Error computing pre-interview score for {inter}") from None
        inter.school_pre_observed_score_of_student = val
        inter.save(update_fields=["school_pre_observed_score_of_student"])


def compute_students_pre_rankings(simulation: Simulation):
    """Compute students' pre-interview rankings of schools.

    For each student, ranks their schools by student_pre_observed_score_of_school.
    Highest score gets rank 1.
    """
    from .models import Interview as InterviewModel

    # Group interviews by student
    students = simulation.students.all()

    for student in students:
        # Get all interviews for this student with non-null scores
        interviews = InterviewModel.objects.filter(
            simulation=simulation, student=student, student_pre_observed_score_of_school__isnull=False
        ).order_by("-student_pre_observed_score_of_school")  # Highest score first

        # Assign rankings (1 = highest score)
        for rank, interview in enumerate(interviews, 1):
            interview.students_pre_rank_of_school = rank
            interview.save(update_fields=["students_pre_rank_of_school"])


def compute_schools_pre_rankings(simulation: Simulation):
    """Compute schools' pre-interview rankings of students.

    For each school, ranks their students by school_pre_observed_score_of_student.
    Highest score gets rank 1.
    """
    from .models import Interview as InterviewModel

    # Group interviews by school
    schools = simulation.schools.all()

    for school in schools:
        # Get all interviews for this school with non-null scores
        interviews = InterviewModel.objects.filter(
            simulation=simulation, school=school, school_pre_observed_score_of_student__isnull=False
        ).order_by("-school_pre_observed_score_of_student")  # Highest score first

        # Assign rankings (1 = highest score)
        for rank, interview in enumerate(interviews, 1):
            interview.schools_pre_rank_of_student = rank
            interview.save(update_fields=["schools_pre_rank_of_student"])


def compute_pre_interview_scores_and_rankings(simulation: Simulation):
    """Complete pre-interview process: scoring and ranking.

    Performs all pre-interview steps in sequence:
    1. Students rate schools (compute observed scores)
    2. Schools rate students (compute observed scores)
    3. Compute student rankings of schools
    4. Compute school rankings of students
    """
    # Step 1: Students rate schools
    students_rate_schools_pre_interview(simulation)

    # Step 2: Schools rate students
    schools_rate_students_pre_interview(simulation)

    # Step 3: Compute student rankings
    compute_students_pre_rankings(simulation)

    # Step 4: Compute school rankings
    compute_schools_pre_rankings(simulation)


def interview(self):
    """Students and schools interview each other.

    Students and Schools update their ratings after the interview.
    """
    pass


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
