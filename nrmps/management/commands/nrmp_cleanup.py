"""Housekeeping, meant to run daily (for example as a Railway cron job).

    python manage.py nrmp_cleanup

- marks runs that stayed queued or running longer than NRMP_STALE_RUN_MINUTES as failed (their worker stopped);
- keeps the newest NRMP_RUNS_KEPT finished runs of each simulation and deletes older ones;
- deletes rate-limit counters older than two days, worker heartbeats older than a day and finished task records
  older than a week.
"""

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from nrmps.models import RateLimitCounter, SimulationRun, WorkerHeartbeat
from nrmps.runs import interrupt_stale_runs


class Command(BaseCommand):
    """Clean up interrupted and old runs and expired bookkeeping rows."""

    help = "Mark interrupted runs as failed and delete old runs, rate-limit counters, heartbeats and task records."

    def handle(self, *args: Any, **options: Any) -> None:
        """Do the clean-up and report what changed."""
        now = timezone.now()
        interrupted = interrupt_stale_runs(timedelta(minutes=settings.NRMP_STALE_RUN_MINUTES))
        old_runs: list[int] = []
        simulations = SimulationRun.objects.values_list("simulation_id", flat=True).distinct()
        for simulation_id in simulations:
            finished = SimulationRun.objects.filter(simulation_id=simulation_id).exclude(
                status__in=SimulationRun.ACTIVE
            )
            old_runs.extend(finished.order_by("-number").values_list("pk", flat=True)[settings.NRMP_RUNS_KEPT :])
        deleted_runs = SimulationRun.objects.filter(pk__in=old_runs).delete()[1].get("nrmps.SimulationRun", 0)
        counters = RateLimitCounter.objects.filter(window_start__lt=now - timedelta(days=2)).delete()[0]
        heartbeats = WorkerHeartbeat.objects.filter(last_seen__lt=now - timedelta(days=1)).delete()[0]
        tasks = DBTaskResult.objects.finished().filter(finished_at__lt=now - timedelta(days=7)).delete()[0]
        self.stdout.write(
            f"Interrupted runs marked failed: {interrupted}. Old runs deleted: {deleted_runs}. "
            f"Rate-limit counters: {counters}. Heartbeats: {heartbeats}. Task records: {tasks}."
        )
