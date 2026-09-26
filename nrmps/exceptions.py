"""Domain errors raised by simulation steps.

These describe problems with a simulation's data or settings that the user can fix, so views show their message
instead of returning a server error. Anything else is a bug and should propagate.
"""


class SimulationError(Exception):
    """A simulation step cannot run; the message tells the user why and what to do."""


class MissingConfigError(SimulationError):
    """The simulation has no saved configuration."""

    def __init__(self, message: str = "This simulation has no configuration yet. Save the configuration first."):
        super().__init__(message)


class PopulationError(SimulationError):
    """The applicant or program population is missing or inconsistent."""


class SizeLimitError(SimulationError):
    """The requested market is larger than the current size limit."""
