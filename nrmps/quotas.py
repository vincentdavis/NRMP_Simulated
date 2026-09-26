"""Per-account quotas (plan step 2.5; ENG-5, CRIT-6). Staff accounts are exempt.

- With `NRMP_REQUIRE_VERIFIED_EMAIL`, accounts must confirm their email address before they can run simulations.
- At most `NRMP_MAX_SIMULATIONS` simulations per account.
- At most `NRMP_RUNS_PER_DAY` runs and `NRMP_PAIRS_PER_DAY` applicant x program pairs per account in any 24 hours.
"""

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import F, Sum
from django.utils import timezone

from .exceptions import SimulationError


class QuotaError(SimulationError):
    """An account has reached one of its quotas; the message says which and what to do."""


def _exempt(user: Any) -> bool:
    return not getattr(user, "is_authenticated", False) or getattr(user, "is_staff", False)


def check_simulation_quota(user: Any) -> None:
    """Raise QuotaError if `user` may not create another simulation."""
    if _exempt(user):
        return
    if user.simulations.count() >= settings.NRMP_MAX_SIMULATIONS:
        raise QuotaError(
            f"You have {settings.NRMP_MAX_SIMULATIONS} simulations, the most one account can have. Delete one to "
            "create another."
        )


def usage_today(user: Any) -> tuple[int, int]:
    """Return (runs, pairs) that `user` started in the last 24 hours."""
    from .models import SimulationRun

    runs = SimulationRun.objects.filter(created_by=user, created_at__gte=timezone.now() - timedelta(days=1))
    totals = runs.aggregate(pairs=Sum(F("n_applicants") * F("n_programs")))
    return runs.count(), int(totals["pairs"] or 0)


def check_run_quota(user: Any, pairs: int) -> None:
    """Raise QuotaError if `user` may not start a run of `pairs` applicant x program pairs now."""
    if _exempt(user):
        return
    if settings.NRMP_REQUIRE_VERIFIED_EMAIL and not user.email_verified:
        raise QuotaError("Confirm your email address to run simulations: see your account page for the link.")
    runs, used = usage_today(user)
    if runs >= settings.NRMP_RUNS_PER_DAY:
        raise QuotaError(
            f"You have started {runs:,} runs in the last 24 hours, the most one account can. Please try again later."
        )
    if used + pairs > settings.NRMP_PAIRS_PER_DAY:
        raise QuotaError(
            f"This run would bring your last 24 hours to {used + pairs:,} applicant \u00d7 program pairs, above the "
            f"daily limit of {settings.NRMP_PAIRS_PER_DAY:,}. Try a smaller market or try again later."
        )
