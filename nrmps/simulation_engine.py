from nrmps.models import Simulation


class InterviewEngine:
    """This class is responsible for running the interview part of the simulation.
    1. Schools invite students based only on score i.e. Schools invite top X% of students always
    2.

    Steps:
    """

    def __init__(self, simulation):
        self.simulation: Simulation = simulation

    def students_rate_schools(self):
        """Students choose which schools they would like to apply to.

        Steps:
        1. Computes the students rating of each school.
        2. Choose which schools to apply to.
        """
        pass

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


class MatchEngine:
    """This class is responsible for running the match part of the simulation."""

    def __init__(self, simulation):
        self.simulation: Simulation = simulation

    def students_rank(self):
        """Each student, using the post-interview rating, chooses which schools to rank and ranks them by rating.
        1 is the highest rank
        """
        pass

    def schools_rank(self):
        """Each school, using the post-interview rating, chooses which students to rank and ranks them by rating."""
        pass

    def match(self):
        """Run the NRMP match algorithm."""
        pass
