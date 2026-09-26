"""Shared fixtures for the nrmps test suite."""

import pytest

PASSWORD = "Correct-Horse-Battery-9"

# A configuration that is valid and gives a small, balanced market (20 applicants, 4 programs x 5 positions).
SMALL_CONFIG = {
    "number_of_applicants": 20,
    "number_of_schools": 4,
    "applicant_score_mean": 0.7,
    "applicant_score_stddev": 0.1,
    "applicant_interview_limit": 5,
    "applicant_meta_preference": ["program_size", "reputation", "location"],
    "applicant_meta_preference_stddev": 0.3,
    "applicant_meta_scores_stddev": 0.1,
    "applicant_pre_interview_rating_error": 0.1,
    "applicant_post_interview_rating_error": 0.02,
    "school_score_mean": 0.5,
    "school_score_stddev": 0.1,
    "school_capacity_mean": 5,
    "school_capacity_stddev": 1,
    "school_interview_limit": 0.1,
    "school_meta_preference": ["board_scores", "research", "honors"],
    "school_meta_preference_stddev": 0.3,
    "school_meta_scores_stddev": 0.1,
    "school_pre_interview_rating_error": 0.1,
    "school_post_interview_rating_error": 0.02,
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
    """Return a simulation owned by `user` with a saved configuration but no populations."""
    from nrmps.models import Simulation, SimulationConfig

    sim = Simulation.objects.create(owner=user, name="Test simulation")
    SimulationConfig.objects.create(simulation=sim, **SMALL_CONFIG)
    return sim


@pytest.fixture
def populated_simulation(simulation):
    """Return the `simulation` fixture with generated students and schools."""
    simulation.create_students()
    simulation.create_schools()
    return simulation
