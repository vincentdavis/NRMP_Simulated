"""`manage.py nrmp_run`: the headless engine (plan steps 2.2 and 3.7, CRIT-8)."""

import io
import json

import pytest
from django.core.management import CommandError, call_command

from nrmps.engine import ENGINE_VERSION, MODEL_VERSION


def _run(*args, **options) -> str:
    out = io.StringIO()
    call_command("nrmp_run", *args, stdout=out, **options)
    return out.getvalue()


def test_same_seed_writes_identical_files(tmp_path):
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"market": {"n_applicants": 200}}))
    _run(params=params, seed=5, out=tmp_path / "a")
    _run(params=params, seed=5, out=tmp_path / "b")
    for name in ("params.json", "population.npz", "results.npz", "stages.npz"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    record = json.loads((tmp_path / "a" / "metrics.json").read_text())
    assert record["seed"] == 5
    assert record["stamps"]["model_version"] == MODEL_VERSION
    assert record["stamps"]["engine_version"] == ENGINE_VERSION
    assert json.loads((tmp_path / "a" / "params.json").read_text())["run"]["seed"] == 5


def test_reusing_a_population_gives_the_same_metrics(tmp_path):
    _run(seed=9, out=tmp_path)
    first = json.loads(_run(seed=9, json=True))
    again = json.loads(_run(seed=9, population=tmp_path / "population.npz", json=True))
    assert first["metrics"] == again["metrics"]
    assert first["population_digest"] == again["population_digest"]


def test_summary_output():
    text = _run(seed=1)
    assert text.startswith("Seed 1: 1,000 applicants, 142 programs, 926 positions")
    assert "agreement 0.6" in text
    assert "applicants with a list matched" in text
    assert "checks passed" in text


def test_invalid_parameters_are_reported(tmp_path):
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"market": {"n_programs": 5000}}))
    with pytest.raises(CommandError, match="5,000 programs need at least"):
        _run(params=params, seed=1)
    with pytest.raises(CommandError, match="Invalid seed"):
        _run(seed=-3)
