"""Organise and reuse (plan step 4.6): the list, duplicate, parameter files and saved presets."""

import io
import json

import pytest
from django.urls import reverse

from nrmps.models import PopulationUpload, SavedPreset, Simulation
from nrmps.params import SimulationParams, load_params
from nrmps.pipeline import StageState, pipeline_summary
from nrmps.presets import preset_options, resolve_preset

from .conftest import SMALL_PARAMS

pytestmark = pytest.mark.django_db


def _manage(sim) -> str:
    return reverse("nrmps:simulation_manage", kwargs={"pk": sim.pk})


# --- The list --------------------------------------------------------------------------------------------------


def test_the_list_shows_market_state_and_match_rate(auth_client, finished_run, simulation):
    body = auth_client.get(reverse("nrmps:simulation_list")).content.decode()
    assert "60 \u00d7 8" in body  # multiplication sign
    assert "Up to date" in body
    assert f"{finished_run.metrics['outcomes']['match']['match_rate'] * 100:.1f}%" in body
    assert f'action="{reverse("nrmps:simulation_duplicate", kwargs={"pk": simulation.pk})}"' in body


@pytest.mark.parametrize(
    ("states", "word"),
    [
        (["done", "done"], "Up to date"),
        (["done", "stale"], "Out of date"),
        (["ready", "ready"], "Not run yet"),
        (["running", "running"], "Running"),
        (["ready", "failed"], "Failed"),
        (["blocked", "blocked"], "Invalid parameters"),
    ],
)
def test_the_pipeline_summary(states, word):
    assert pipeline_summary([StageState(str(k), str(k), state) for k, state in enumerate(states)])[0] == word


# --- Duplicate -----------------------------------------------------------------------------------------------------


def test_duplicating_copies_parameters_seed_and_uploads_but_not_runs(auth_client, finished_run, simulation):
    PopulationUpload.objects.create(
        simulation=simulation, side="programs", filename="p.csv", rows=8, data=b"x", digest="d"
    )
    response = auth_client.post(reverse("nrmps:simulation_duplicate", kwargs={"pk": simulation.pk}))
    copy = Simulation.objects.exclude(pk=simulation.pk).get()
    assert response["Location"] == _manage(copy)
    assert copy.name == f"Copy of {simulation.name}"
    assert copy.params == simulation.params
    assert not copy.runs.exists()
    assert copy.uploads.get().filename == "p.csv"
    assert simulation.uploads.count() == 1


def test_duplicating_respects_ownership_and_quotas(client, auth_client, other_user, simulation, settings):
    client.force_login(other_user)
    assert client.post(reverse("nrmps:simulation_duplicate", kwargs={"pk": simulation.pk})).status_code == 404
    settings.NRMP_MAX_SIMULATIONS = 1
    auth_client.post(reverse("nrmps:simulation_duplicate", kwargs={"pk": simulation.pk}))
    assert Simulation.objects.count() == 1


# --- Parameter files -------------------------------------------------------------------------------------------------


def _upload(content: bytes, name: str = "params.json") -> io.BytesIO:
    file = io.BytesIO(content)
    file.name = name
    return file


def test_the_parameters_download_and_load_back(auth_client, simulation, user):
    response = auth_client.get(reverse("nrmps:params_export", kwargs={"pk": simulation.pk}))
    assert response["Content-Disposition"] == 'attachment; filename="test-simulation-parameters.json"'
    data = json.loads(response.content)
    assert data == simulation.params
    other = Simulation.objects.create(owner=user, name="Other")
    auth_client.post(reverse("nrmps:params_import", kwargs={"pk": other.pk}), {"file": _upload(response.content)})
    other.refresh_from_db()
    assert other.params == simulation.params


def test_a_file_without_a_seed_keeps_the_simulations_seed(auth_client, simulation):
    seed = simulation.get_params().run.seed
    data = SimulationParams.model_validate({"market": {"n_applicants": 70, "n_programs": 8}}).to_json_data()
    auth_client.post(
        reverse("nrmps:params_import", kwargs={"pk": simulation.pk}), {"file": _upload(json.dumps(data).encode())}
    )
    simulation.refresh_from_db()
    params = simulation.get_params()
    assert (params.market.n_applicants, params.run.seed) == (70, seed)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not json", "The file is not JSON"),
        (json.dumps({"market": {"n_applicants": -5}}).encode(), "The parameters in the file are not valid: market"),
        (b" " * 100_001, "at most 100 kB"),
    ],
)
def test_bad_parameter_files_change_nothing(auth_client, simulation, content, message):
    before = simulation.params
    url = reverse("nrmps:params_import", kwargs={"pk": simulation.pk})
    response = auth_client.post(url, {"file": _upload(content)}, follow=True)
    assert message in response.content.decode()
    simulation.refresh_from_db()
    assert simulation.params == before


def test_parameter_files_are_private(client, other_user, simulation):
    client.force_login(other_user)
    assert client.get(reverse("nrmps:params_export", kwargs={"pk": simulation.pk})).status_code == 404
    url = reverse("nrmps:params_import", kwargs={"pk": simulation.pk})
    assert client.post(url, {"file": _upload(b"{}")}).status_code == 404


# --- Saved presets ---------------------------------------------------------------------------------------------------


def _save_preset(client, sim, name="Mine", description="My market"):
    return client.post(_manage(sim), {"form_id": "save_preset", "name": name, "description": description}, follow=True)


def test_saving_a_preset_stores_the_parameters_without_the_seed(auth_client, simulation, user):
    body = _save_preset(auth_client, simulation).content.decode()
    assert "Saved the parameters as the preset “Mine”" in body
    preset = SavedPreset.objects.get(owner=user)
    assert preset.params["run"]["seed"] is None
    assert load_params(preset.params) == simulation.get_params().with_seed(None)
    assert "Mine" in auth_client.get(reverse("nrmps:simulation_list")).content.decode()


@pytest.mark.parametrize(("name", "message"), [("", "Give the preset a name."), ("Mine", "You already have a preset")])
def test_preset_names_are_required_and_unique(auth_client, simulation, name, message):
    _save_preset(auth_client, simulation)
    assert message in _save_preset(auth_client, simulation, name=name).content.decode()


def test_the_preset_quota(auth_client, simulation, settings):
    settings.NRMP_MAX_PRESETS = 0
    assert "the most one account can have" in _save_preset(auth_client, simulation).content.decode()
    assert not SavedPreset.objects.exists()


def test_new_simulations_can_start_from_a_saved_preset(auth_client, simulation, user):
    _save_preset(auth_client, simulation)
    preset = SavedPreset.objects.get()
    page = auth_client.get(reverse("nrmps:simulation_create")).content.decode()
    assert f'value="user:{preset.pk}"' in page
    assert "Yours" in page
    auth_client.post(reverse("nrmps:simulation_create"), {"name": "From mine", "preset": f"user:{preset.pk}"})
    new = Simulation.objects.get(name="From mine")
    assert new.get_params().with_seed(None) == simulation.get_params().with_seed(None)
    assert new.get_params().run.seed is not None


def test_a_saved_preset_can_be_applied_to_another_simulation(auth_client, simulation, user):
    _save_preset(auth_client, simulation)
    preset = SavedPreset.objects.get()
    other = Simulation.objects.create(owner=user, name="Other")
    seed = other.get_params().run.seed
    auth_client.post(_manage(other), {"form_id": "preset", "preset": f"user:{preset.pk}"})
    other.refresh_from_db()
    assert other.get_params() == simulation.get_params().with_seed(seed)


def test_presets_of_other_users_cannot_be_used_or_deleted(client, other_user, simulation, user):
    SavedPreset.objects.create(owner=user, name="Private", params=SimulationParams().with_seed(None).to_json_data())
    preset = SavedPreset.objects.get()
    assert [option.key for option in preset_options(other_user) if option.own] == []
    with pytest.raises(KeyError):
        resolve_preset(other_user, f"user:{preset.pk}", 1)
    client.force_login(other_user)
    assert client.post(reverse("nrmps:preset_delete", kwargs={"preset_id": preset.pk})).status_code == 404
    assert SavedPreset.objects.exists()


def test_deleting_a_preset(auth_client, simulation, user):
    _save_preset(auth_client, simulation)
    preset = SavedPreset.objects.get()
    response = auth_client.post(reverse("nrmps:preset_delete", kwargs={"preset_id": preset.pk}), follow=True)
    assert "Deleted the preset “Mine”." in response.content.decode()
    assert not SavedPreset.objects.exists()


def test_a_saved_preset_that_no_longer_fits_is_reported(auth_client, simulation, user):
    broken = SavedPreset.objects.create(
        owner=user, name="Old", params={"schema_version": 1, "market": {"n_applicants": -1}}
    )
    response = auth_client.post(_manage(simulation), {"form_id": "preset", "preset": f"user:{broken.pk}"}, follow=True)
    assert "no longer fits the parameters" in response.content.decode()
    assert simulation.get_params() == load_params(SMALL_PARAMS)
