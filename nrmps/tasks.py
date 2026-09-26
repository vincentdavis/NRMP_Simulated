"""Background tasks (plan step 2.5, decision D5): django.tasks, executed by the configured TASKS backend.

With the immediate backend a task runs inside `enqueue()`, in the web request; with the django-tasks-db backend it
is stored in the database and a worker service (`manage.py nrmp_worker`) runs it.
"""

from django.tasks import task

from .runs import execute_run


@task()
def execute_run_task(run_id: int) -> None:
    """Execute a queued run (see `runs.execute_run`); problems are recorded on the run itself."""
    execute_run(run_id)
