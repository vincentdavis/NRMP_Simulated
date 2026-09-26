"""Concurrent runs of one simulation cannot both start (plan steps 0.4 and 2.3, CRIT-1).

Starting a run locks the simulation row and a partial unique constraint allows one queued or running run per
simulation. These tests need real row locks, so they run on PostgreSQL only (set NRMP_TEST_DATABASE_URL); SQLite
serialises writes differently.
"""

import threading

import pytest
from django.db import connection

from nrmps.models import Simulation, SimulationRun
from nrmps.runs import RunInProgressError, start_run

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="needs PostgreSQL row locks"),
]


def _run_concurrently(action, n: int = 2) -> list[Exception]:
    """Start `n` threads that call `action()` at the same moment; return the exceptions they raised."""
    barrier = threading.Barrier(n)
    errors: list[Exception] = []

    def worker():
        try:
            barrier.wait()
            action()
        except Exception as exc:
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


def test_two_simultaneous_runs_start_only_one(simulation, user):
    errors = _run_concurrently(lambda: start_run(Simulation.objects.get(pk=simulation.pk), user))
    assert len(errors) == 1
    assert isinstance(errors[0], RunInProgressError)
    assert SimulationRun.objects.filter(simulation=simulation).count() == 1


def test_the_database_allows_one_active_run_per_simulation(simulation, user):
    from django.db import IntegrityError, transaction

    run = start_run(simulation, user)
    with pytest.raises(IntegrityError), transaction.atomic():
        SimulationRun.objects.create(
            simulation=simulation,
            number=2,
            params=run.params,
            params_hash=run.params_hash,
            seed=run.seed,
            **run.stamps(),
        )
