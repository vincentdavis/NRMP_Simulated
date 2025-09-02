from nrmps.models import Interview, Simulation


def _score(meta_scores: dict[str:float], meta_preferances: dict[str:float], rating_error) -> float:
    """Compute the score for a student based on the meta-scores and the score.
    Calculating:
    - sum(meta_score * meta_preference)*rating_error.
    """
    return sum(meta_scores[meta] * meta_preferances[meta] for meta in meta_preferances) * rating_error


def initialize_interview(simulation: Simulation):
    """Initialize the interview objects for each student and school of a simulation."""
    for student in simulation.students.all():
        for school in simulation.schools.all():
            Interview.objects.create(student=student, school=school)


def students_rate_schools_pre_interview(simulation: Simulation):
    """Students choose which schools they would like to apply to.

    Steps:
    1. Computes the students rating of each school.
    2. Choose which schools to apply to.

    Details:
    - Compute each student's pre-interview observed score of each school.
    _score(School.score_meta, Student.meta_preference, Student.pre_interview_rating_error)
    """
    for inter in simulation.interview.all():
        inter.update(
            student_pre_observed_score_of_school=_score(
                inter.school.score_meta,
                inter.student.meta_preference,
                inter.student.pre_interview_rating_error,
            )
        )


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
