"""Shared fixtures for the nrmps test suite."""

import pytest

PASSWORD = "Correct-Horse-Battery-9"

# Parameters for a small, fast market: 60 applicants, 50 positions, 8 programs (480 pairs), with a fixed seed.
SMALL_PARAMS = {
    "schema_version": 1,
    "run": {"seed": 12345},
    "market": {"n_applicants": 60, "applicants_per_position": 1.2, "n_programs": 8},
}


@pytest.fixture
def user(django_user_model):
    """Return a regular (non-staff) user."""
    return django_user_model.objects.create_user("alice", email="alice@example.com", password=PASSWORD)


@pytest.fixture
def other_user(django_user_model):
    """Return a second regular user, who does not own the test simulation."""
    return django_user_model.objects.create_user("mallory", email="mallory@example.com", password=PASSWORD)


@pytest.fixture
def auth_client(client, user):
    """Return a test client logged in as `user`."""
    client.force_login(user)
    return client


@pytest.fixture
def simulation(user):
    """Return a simulation owned by `user` with small parameters and no runs."""
    from nrmps.models import Simulation
    from nrmps.params import load_params

    return Simulation.objects.create(
        owner=user, name="Test simulation", params=load_params(SMALL_PARAMS).to_json_data()
    )


@pytest.fixture
def finished_run(simulation, user):
    """Return a successful run of the `simulation` fixture."""
    from nrmps.runs import run_now

    run = run_now(simulation, user)
    assert run.status == "succeeded", run.error
    return run
