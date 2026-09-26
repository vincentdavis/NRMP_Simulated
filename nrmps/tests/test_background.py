"""Background runs, the worker, quotas, rate limits and operations (plan step 2.5)."""

import io
import threading
from datetime import timedelta

import pytest
from asgiref.local import Local
from django.core import mail
from django.core.management import call_command
from django.tasks import task_backends
from django.urls import reverse
from django.utils import timezone

from nrmps.management.commands.nrmp_worker import beat
from nrmps.models import RateLimitCounter, Simulation, SimulationRun, WorkerHeartbeat
from nrmps.quotas import QuotaError, check_run_quota
from nrmps.ratelimit import hit, parse_rate
from nrmps.runs import dispatch_run, run_now, start_run

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def _reset_task_backends():
    task_backends.__dict__.pop("settings", None)
    task_backends._settings = None
    task_backends._connections = Local(task_backends.thread_critical)


@pytest.fixture
def database_tasks(settings):
    """Queue runs in the database for a worker, as with TASK_BACKEND=database."""
    settings.TASK_BACKEND = "database"
    settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend", "QUEUES": ["default"]}}
    _reset_task_backends()
    yield
    _reset_task_backends()


def _start(client, sim, **data):
    return client.post(reverse("nrmps:run_start", kwargs={"pk": sim.pk}), data, headers={"hx-request": "true"})


# --- Task backends and the worker ------------------------------------------------------------------------------------


def test_immediate_backend_runs_inside_the_request(simulation, user):
    run = dispatch_run(start_run(simulation, user))
    assert run.status == SimulationRun.Status.SUCCEEDED


@pytest.mark.django_db(transaction=True)
def test_database_backend_queues_the_run_for_the_worker(database_tasks, auth_client, simulation):
    response = _start(auth_client, simulation)
    assert "Run 1 is queued." in response.headers["HX-Trigger"]
    run = simulation.runs.get()
    assert run.status == SimulationRun.Status.QUEUED
    body = response.content.decode()
    assert 'hx-trigger="every 1s"' in body  # the panel polls
    assert "Email me when it finishes" in body
    assert "Run</button>" not in body.replace("\n", "").replace("  ", "")  # no second run while one is queued
    progress = auth_client.get(reverse("nrmps:run_progress", kwargs={"pk": simulation.pk, "number": 1}))
    assert b"This run is queued: 0%." in progress.content

    call_command("nrmp_worker", batch=True, startup_delay=False, reload=False, verbosity=0)

    run.refresh_from_db()
    assert run.status == SimulationRun.Status.SUCCEEDED
    status = auth_client.get(reverse("nrmps:run_status", kwargs={"pk": simulation.pk}), {"run": "1"})
    assert "Run 1 finished." in status.headers["HX-Trigger"]
    assert 'hx-trigger="every 1s"' not in status.content.decode()  # polling stops
    progress = auth_client.get(reverse("nrmps:run_progress", kwargs={"pk": simulation.pk, "number": 1}))
    assert progress["HX-Refresh"] == "true"


def test_heartbeat_records_the_worker():
    stop = threading.Event()
    stop.set()
    beat("worker-1", stop, own_thread=False)
    heartbeat = WorkerHeartbeat.objects.get(worker_id="worker-1")
    assert heartbeat.last_seen >= heartbeat.started_at


def test_health_check_reports_the_queue_and_the_worker(client, settings):
    body = client.get(reverse("nrmps:healthz")).json()
    assert body == {"status": "ok", "tasks": {"backend": "immediate", "queued": 0, "running": 0}}
    settings.TASK_BACKEND = "database"
    assert client.get(reverse("nrmps:healthz")).json()["tasks"]["worker"] == "missing"
    now = timezone.now()
    WorkerHeartbeat.objects.create(worker_id="w", started_at=now, last_seen=now)
    tasks = client.get(reverse("nrmps:healthz")).json()["tasks"]
    assert tasks["worker"] == "ok"
    assert tasks["worker_last_seen_seconds"] <= 1


def test_the_worker_takes_larger_markets(settings):
    from nrmps.limits import max_pairs

    settings.NRMP_MAX_PAIRS, settings.NRMP_MAX_PAIRS_WORKER = 100, 5000
    assert max_pairs() == 100
    settings.TASK_BACKEND = "database"
    assert max_pairs() == 5000


# --- "Run finished" email -------------------------------------------------------------------------------------------


def test_run_finished_email_goes_to_confirmed_owners_who_asked(simulation, user):
    user.email_verified_at = timezone.now()
    user.save()
    run = dispatch_run(start_run(simulation, user, notify=True))
    assert run.status == SimulationRun.Status.SUCCEEDED
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["alice@example.com"]
    assert message.subject == "Run 1 of “Test simulation” finished"
    assert f"/simulations/{simulation.pk}/runs/1/" in message.body


def test_no_email_without_asking_or_without_a_confirmed_address(simulation, user):
    dispatch_run(start_run(simulation, user, notify=True))  # address not confirmed
    user.email_verified_at = timezone.now()
    user.save()
    dispatch_run(start_run(simulation, user))  # not asked
    assert mail.outbox == []


# --- Quotas -----------------------------------------------------------------------------------------------------------


def test_runs_per_day_quota(simulation, user, settings):
    settings.NRMP_RUNS_PER_DAY = 2
    run_now(simulation, user)
    run_now(simulation, user)
    with pytest.raises(QuotaError, match="started 2 runs in the last 24 hours"):
        start_run(simulation, user)


def test_pairs_per_day_quota(simulation, user, settings):
    settings.NRMP_PAIRS_PER_DAY = 700
    run_now(simulation, user)  # 480 pairs
    with pytest.raises(QuotaError, match="960 applicant \u00d7 program pairs, above the daily limit of 700"):
        start_run(simulation, user)


def test_unverified_accounts_can_be_required_to_confirm_first(simulation, user, settings):
    settings.NRMP_REQUIRE_VERIFIED_EMAIL = True
    with pytest.raises(QuotaError, match="Confirm your email address"):
        check_run_quota(user, 10)
    user.email_verified_at = timezone.now()
    check_run_quota(user, 10)


def test_staff_and_commands_have_no_quota(simulation, user, settings):
    settings.NRMP_RUNS_PER_DAY = 0
    settings.NRMP_REQUIRE_VERIFIED_EMAIL = True
    run_now(simulation, None)
    user.is_staff = True
    run_now(simulation, user)


def test_simulations_per_account_quota(auth_client, simulation, settings):
    settings.NRMP_MAX_SIMULATIONS = 1
    response = auth_client.post(reverse("nrmps:simulation_create"), {"name": "Second"})
    assert response.status_code == 200
    assert "You have 1 simulations, the most one account can have." in response.content.decode()
    assert Simulation.objects.count() == 1


def test_quota_errors_are_shown_on_the_page(auth_client, simulation, settings):
    settings.NRMP_RUNS_PER_DAY = 0
    response = _start(auth_client, simulation)
    assert "the most one account can" in response.content.decode()


# --- Rate limits -----------------------------------------------------------------------------------------------------


def test_parse_rate():
    assert parse_rate("10/h") == (10, 3600)
    assert parse_rate("3/s") == (3, 1)
    for bad in ("10", "x/h", "10/w", "-1/m"):
        with pytest.raises(ValueError, match="Invalid rate"):
            parse_rate(bad)


def test_hits_are_counted_per_key_and_window():
    assert not hit("k", "2/h")
    assert not hit("k", "2/h")
    assert hit("k", "2/h")
    assert not hit("other", "2/h")
    assert RateLimitCounter.objects.get(key="k").count == 3


def test_signups_are_limited_per_client_address(client, settings):
    settings.NRMP_RATE_LIMITS = settings.NRMP_RATE_LIMITS | {"signup": "2/h"}
    url = reverse("nrmps:signup")
    for number in range(2):
        data = {
            "username": f"u{number}",
            "email": f"u{number}@example.com",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        client.post(url, data)
        client.logout()
    response = client.post(
        url, {"username": "u9", "email": "u9@example.com", "password1": PASSWORD, "password2": PASSWORD}
    )
    assert response.status_code == 429
    assert "Too many requests" in response.content.decode()


def test_runs_are_limited_per_account(auth_client, simulation, settings):
    settings.NRMP_RATE_LIMITS = settings.NRMP_RATE_LIMITS | {"run": "1/h"}
    assert _start(auth_client, simulation).status_code == 200
    response = _start(auth_client, simulation)
    assert response.status_code == 429
    assert simulation.runs.count() == 1


def test_save_and_run_respects_the_run_limit(auth_client, simulation, settings):
    from nrmps.params_forms import post_data

    settings.NRMP_RATE_LIMITS = settings.NRMP_RATE_LIMITS | {"run": "0/h"}
    data = post_data(simulation.get_params()) | {"form_id": "params", "run": "1"}
    response = auth_client.post(reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk}), data, follow=True)
    assert "Parameters saved, but not run: Too many requests." in response.content.decode()
    assert not simulation.runs.exists()


# --- Sign-up honeypot -------------------------------------------------------------------------------------------------


def test_signup_honeypot_rejects_bots(client):
    from nrmps.models import User

    data = {"username": "bot", "email": "bot@example.com", "password1": PASSWORD, "password2": PASSWORD}
    response = client.post(reverse("nrmps:signup"), data | {"website": "http://spam.example"})
    assert response.status_code == 200
    assert "The account could not be created." in response.content.decode()
    assert not User.objects.filter(username="bot").exists()
    body = client.get(reverse("nrmps:signup")).content.decode()
    assert 'aria-hidden="true"' in body
    assert 'name="website"' in body


# --- Housekeeping and the ops page ------------------------------------------------------------------------------------


def test_cleanup_interrupts_stale_runs_and_prunes_old_ones(simulation, user, settings):
    settings.NRMP_RUNS_KEPT = 2
    for _ in range(3):
        run_now(simulation, user)
    stuck = start_run(simulation, user)
    SimulationRun.objects.filter(pk=stuck.pk).update(created_at=timezone.now() - timedelta(hours=3))
    RateLimitCounter.objects.create(key="old", window_start=timezone.now() - timedelta(days=5), count=1)
    out = io.StringIO()
    call_command("nrmp_cleanup", stdout=out)
    stuck.refresh_from_db()
    assert stuck.status == SimulationRun.Status.FAILED
    assert "interrupted" in stuck.error
    # Of the four finished runs (three succeeded, one interrupted) the newest two are kept.
    assert sorted(simulation.runs.values_list("number", flat=True)) == [3, 4]
    assert not RateLimitCounter.objects.filter(key="old").exists()
    assert "Interrupted runs marked failed: 1. Old runs deleted: 2." in out.getvalue()


def test_ops_page_is_for_staff_only(client, auth_client, finished_run, django_user_model):
    url = reverse("nrmps:ops")
    assert client.get(url).status_code == 302
    assert auth_client.get(url).status_code == 302
    staff = django_user_model.objects.create_user("ops", email="ops@example.com", password="x", is_staff=True)
    client.force_login(staff)
    body = client.get(url).content.decode()
    for text in ("Runs per day", "95th percentile", "Largest runs", "Quota use", "Backend: <strong>immediate"):
        assert text in body, text
