"""Concurrent steps on one simulation run one after the other (plan step 0.4, CRIT-1).

Two simultaneous "(re)Create" requests used to double the population, and two "Initialize" requests ended in an
IntegrityError. Steps now lock the simulation row first. These tests need real row locks, so they run on PostgreSQL
only (set NRMP_TEST_DATABASE_URL); SQLite serialises writes differently.
"""

import threading

import pytest
from django.db import connection

from nrmps import simulation_engine as se
from nrmps.models import Interview, Simulation

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


def test_concurrent_population_creation_does_not_double_the_population(simulation):
    simulation.configs.update(number_of_applicants=500)
    errors = _run_concurrently(lambda: Simulation.objects.get(pk=simulation.pk).create_students())
    assert errors == []
    assert simulation.students.count() == 500


def test_concurrent_initialization_does_not_fail(populated_simulation):
    errors = _run_concurrently(lambda: se.initialize_interview(Simulation.objects.get(pk=populated_simulation.pk)))
    assert errors == []
    assert Interview.objects.filter(simulation=populated_simulation).count() == 80
