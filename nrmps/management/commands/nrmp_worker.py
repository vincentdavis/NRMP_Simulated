"""Run the background worker for queued runs, with a heartbeat for /healthz and the ops page.

    python manage.py nrmp_worker

This is django-tasks-db's `db_worker` with the same options, plus a thread that records the worker as alive every
30 seconds (`WorkerHeartbeat`). Use it as the start command of the worker service when TASK_BACKEND=database.
"""

import logging
import socket
import threading
from typing import Any

from django.db import connection
from django.utils import timezone
from django_tasks_db.management.commands.db_worker import Command as DatabaseWorkerCommand

from nrmps.models import WorkerHeartbeat

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 30


def beat(
    worker_id: str, stop: threading.Event, interval: float = HEARTBEAT_SECONDS, *, own_thread: bool = True
) -> None:
    """Record the worker as alive now and then every `interval` seconds until `stop` is set.

    In its own thread (the normal case) it closes that thread's database connection after each write.
    """
    started = timezone.now()
    hostname = socket.gethostname()[:255]
    while True:
        try:
            WorkerHeartbeat.objects.update_or_create(
                worker_id=worker_id,
                defaults={"hostname": hostname, "started_at": started, "last_seen": timezone.now()},
            )
        except Exception:
            logger.exception("Could not record the worker heartbeat")
        finally:
            if own_thread:
                connection.close()
        if stop.wait(interval):
            return


class Command(DatabaseWorkerCommand):
    """django-tasks-db's worker with a heartbeat."""

    help = "Run the background worker for queued runs (django-tasks-db db_worker) with a heartbeat."

    def handle(self, *args: Any, **options: Any) -> None:
        """Start the heartbeat thread, then the worker loop."""
        stop = threading.Event()
        thread = threading.Thread(target=beat, args=(options["worker_id"], stop), daemon=True, name="heartbeat")
        thread.start()
        try:
            super().handle(*args, **options)
        finally:
            stop.set()
