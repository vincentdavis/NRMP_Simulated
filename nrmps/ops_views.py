"""The staff-only operations page (plan step 2.5, CRIT-11): runs per day, failures, durations, the queue and quotas."""

from datetime import timedelta

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import SimulationRun, WorkerHeartbeat
from .views import task_health

DAYS = 14


def _percentile(values: list[int], fraction: float) -> int | None:
    """Return the value at `fraction` of the sorted values (nearest rank), or None without values."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


@staff_member_required
@require_GET
def ops(request):
    """Runs per day, failures, p95 duration, largest runs, the queue, workers and quota use."""
    now = timezone.now()
    recent = SimulationRun.objects.filter(created_at__gte=now - timedelta(days=DAYS))
    failed = Q(status=SimulationRun.Status.FAILED)
    pairs = Sum(F("n_applicants") * F("n_programs"))
    per_day = (
        recent.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(runs=Count("id"), failed=Count("id", filter=failed), pairs=pairs)
        .order_by("-day")
    )
    durations = list(
        recent.filter(status=SimulationRun.Status.SUCCEEDED, duration_ms__isnull=False).values_list(
            "duration_ms", flat=True
        )
    )
    today = SimulationRun.objects.filter(created_at__gte=now - timedelta(days=1))
    context = {
        "days": DAYS,
        "per_day": per_day,
        "median_ms": _percentile(durations, 0.5),
        "p95_ms": _percentile(durations, 0.95),
        "finished": len(durations),
        "failures": recent.filter(failed).select_related("simulation").order_by("-created_at")[:10],
        "largest": recent.annotate(pairs=F("n_applicants") * F("n_programs"))
        .select_related("simulation__owner")
        .order_by("-pairs")[:10],
        "active": SimulationRun.objects.filter(status__in=SimulationRun.ACTIVE)
        .select_related("simulation")
        .order_by("created_at"),
        "workers": WorkerHeartbeat.objects.order_by("-last_seen")[:5],
        "tasks": task_health(),
        "top_users": today.values("created_by__username")
        .annotate(runs=Count("id"), pairs=pairs)
        .order_by("-runs")[:10],
        "quotas": {
            "runs_per_day": settings.NRMP_RUNS_PER_DAY,
            "pairs_per_day": settings.NRMP_PAIRS_PER_DAY,
            "require_verified_email": settings.NRMP_REQUIRE_VERIFIED_EMAIL,
        },
    }
    return render(request, "nrmps/ops.html", context)
