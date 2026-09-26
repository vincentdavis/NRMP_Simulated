"""Size limits for runs (decision D4 in docs/PROJECT_REVIEW.md).

The engine's cost grows with the number of applicant x program pairs, so the limit is on that product. When runs
execute inside the web request (TASK_BACKEND=immediate) they must finish well within the gunicorn timeout
(`NRMP_MAX_PAIRS`); a worker can take larger ones (`NRMP_MAX_PAIRS_WORKER`).
"""

from django.conf import settings

from .exceptions import SizeLimitError


def max_pairs() -> int:
    """Return the largest applicants x programs product of one run: larger when a worker executes runs."""
    if settings.TASK_BACKEND == "database":
        return int(settings.NRMP_MAX_PAIRS_WORKER)
    return int(settings.NRMP_MAX_PAIRS)


def market_size_error(n_applicants: int, n_programs: int) -> str | None:
    """Return a message if applicants x programs is above the limit, else None."""
    pairs = n_applicants * n_programs
    limit = max_pairs()
    if pairs <= limit:
        return None
    return (
        f"{n_applicants:,} applicants x {n_programs:,} programs = {pairs:,} pairs, which is above the current limit "
        f"of {limit:,} pairs. Use fewer applicants or programs."
    )


def check_market_size(n_applicants: int, n_programs: int) -> None:
    """Raise SizeLimitError if applicants x programs is above the limit."""
    if message := market_size_error(n_applicants, n_programs):
        raise SizeLimitError(message)
