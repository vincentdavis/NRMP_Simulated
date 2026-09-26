"""Migration 0014 converts legacy configurations to model 2.0 parameters (plan step 2.3, decision D3)."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("nrmps", "0012_applicant_program_names_and_dead_fields")]


@pytest.mark.django_db(transaction=True)
def test_configurations_become_model_2_parameters():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    old = executor.loader.project_state(BEFORE).apps
    owner = old.get_model("nrmps", "User").objects.create(username="u", email="u@example.com", password="x")
    simulations = old.get_model("nrmps", "Simulation").objects
    configured = simulations.create(owner=owner, name="configured")
    old.get_model("nrmps", "SimulationConfig").objects.create(
        simulation=configured,
        number_of_applicants=300,
        number_of_schools=12,
        school_capacity_mean=20.0,
        applicant_meta_preference=["reputation", "Big City"],
        school_meta_preference=["board_scores", "3rd_year", "board_scores"],
    )
    simulations.create(owner=owner, name="bare")
    student = old.get_model("nrmps", "Student").objects.create(simulation=configured, name="s", score=0.5)
    assert student.pk

    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())

    from nrmps.models import Simulation

    params = Simulation.objects.get(name="configured").get_params()
    assert params.market.n_applicants == 300
    assert params.market.n_programs == 12
    assert params.market.program_size_mean == 20.0
    assert params.market.applicants_per_position == 1.25  # 300 applicants for 12 x 20 positions
    assert [a.key for a in params.programs.attributes] == ["reputation", "big_city"]
    assert params.programs.attributes[0].corr_with_quality == 0.9  # the spec's default for a known attribute
    assert [a.key for a in params.applicants.attributes] == ["board_scores", "a_3rd_year"]
    assert params.run.seed is not None
    bare = Simulation.objects.get(name="bare").get_params()
    assert bare.market.n_applicants == 1000
    assert bare.run.seed is not None
    tables = connection.introspection.table_names()
    assert "nrmps_student" not in tables
    assert "nrmps_simulationconfig" not in tables
