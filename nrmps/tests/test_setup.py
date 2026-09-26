"""The setup form (plan step 4.2): presets, the live preview of what parameters give, and sliders."""

import pytest
from django.urls import reverse

from nrmps.limits import max_pairs
from nrmps.models import PopulationUpload, Simulation
from nrmps.params import SimulationParams, iter_fields
from nrmps.params_forms import ScalarForm, form_name, post_data, slider_step
from nrmps.presets import DEFAULT_PRESET, PRESETS, preset_params
from nrmps.previews import market_preview

pytestmark = pytest.mark.django_db


def _manage(sim) -> str:
    return reverse("nrmps:simulation_manage", kwargs={"pk": sim.pk})


def _preview(sim) -> str:
    return reverse("nrmps:params_preview", kwargs={"pk": sim.pk})


# --- Presets -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("key", list(PRESETS))
def test_every_preset_is_valid_and_runs_without_a_worker(key):
    params = preset_params(key, seed=7)
    assert params.run.seed == 7
    assert params.market.n_applicants * params.n_programs() <= max_pairs()
    assert PRESETS[key].title
    assert PRESETS[key].description


def test_the_default_preset_is_the_defaults():
    assert preset_params(DEFAULT_PRESET, seed=5) == SimulationParams().with_seed(5)
    with pytest.raises(KeyError):
        preset_params("nonsense")


def test_presets_change_only_what_they_say():
    signals = preset_params("signals", seed=1)
    assert [tier.name for tier in signals.signals.tiers] == ["gold", "silver"]
    assert signals.market == SimulationParams().market
    classroom = preset_params("classroom", seed=1)
    assert (classroom.market.n_applicants, classroom.n_programs()) == (60, 8)
    assert classroom.prefs == SimulationParams().prefs


def test_a_new_simulation_starts_from_the_chosen_preset(auth_client):
    page = auth_client.get(reverse("nrmps:simulation_create")).content.decode()
    for preset in PRESETS.values():
        assert preset.title in page
    response = auth_client.post(reverse("nrmps:simulation_create"), {"name": "Class", "preset": "classroom"})
    sim = Simulation.objects.get(name="Class")
    assert response["Location"] == _manage(sim)
    params = sim.get_params()
    assert params.market.n_applicants == 60
    assert params.run.seed is not None
    assert params.with_seed(1) == preset_params("classroom", seed=1)
    invalid = auth_client.post(reverse("nrmps:simulation_create"), {"name": "Bad", "preset": "nonsense"})
    assert invalid.status_code == 200
    assert not Simulation.objects.filter(name="Bad").exists()


def test_applying_a_preset_replaces_the_parameters_and_keeps_the_seed(auth_client, simulation):
    seed = simulation.get_params().run.seed
    response = auth_client.post(_manage(simulation), {"form_id": "preset", "preset": "perfect_information"})
    assert response["Location"].endswith("#parameters")
    simulation.refresh_from_db()
    assert simulation.get_params() == preset_params("perfect_information", seed=seed)
    page = auth_client.get(_manage(simulation)).content.decode()
    assert "Applied the preset “Perfect information”" in page


def test_an_unknown_preset_changes_nothing(auth_client, simulation):
    before = simulation.params
    response = auth_client.post(_manage(simulation), {"form_id": "preset", "preset": "nonsense"}, follow=True)
    assert "Choose one of the presets." in response.content.decode()
    simulation.refresh_from_db()
    assert simulation.params == before


# --- The preview ----------------------------------------------------------------------------------------------------


def test_the_preview_of_the_defaults():
    preview = market_preview(SimulationParams().with_seed(3), {})
    assert (preview.applicants, preview.positions, preview.programs) == (1000, 926, 142)
    assert preview.interview_slots > preview.positions
    assert preview.size_error is None
    assert [picture.title for picture in preview.pictures] == [
        "Applicant strength",
        "Program quality",
        "Positions per program",
    ]
    strength = preview.pictures[0]
    assert strength.path.startswith("M0,56")
    assert "44% around +0.50" in strength.description


def test_the_preview_uses_uploaded_sides(simulation):
    upload = PopulationUpload(simulation=simulation, side="programs", rows=40)
    preview = market_preview(SimulationParams().with_seed(3), {"programs": upload})
    assert preview.programs == 40
    assert preview.positions is None
    assert [picture.title for picture in preview.pictures] == ["Applicant strength"]


def test_the_page_shows_the_preview_of_the_saved_parameters(auth_client, simulation):
    body = auth_client.get(_manage(simulation)).content.decode()
    assert "What these parameters give" in body
    assert f'hx-post="{_preview(simulation)}"' in body
    assert "Positions per program" in body


def test_the_preview_follows_the_edited_parameters_without_saving(auth_client, simulation):
    params = simulation.get_params()
    data = post_data(params) | {"form_id": "params", "market__n_applicants": "2000"}
    response = auth_client.post(_preview(simulation), data)
    assert response.status_code == 200
    body = response.content.decode()
    assert "2,000" in body
    simulation.refresh_from_db()
    assert simulation.get_params() == params  # nothing saved


def test_the_preview_lists_what_to_fix(auth_client, simulation):
    data = post_data(simulation.get_params()) | {"market__n_applicants": "-5"}
    body = auth_client.post(_preview(simulation), data).content.decode()
    assert "Fix these to see what the parameters give" in body


def test_the_preview_reports_a_market_above_the_limit(auth_client, simulation, settings):
    settings.NRMP_MAX_PAIRS = 100  # the fixture's market has 480 pairs
    body = auth_client.post(_preview(simulation), post_data(simulation.get_params())).content.decode()
    assert "above the current limit of 100 pairs" in body


def test_only_the_owner_gets_the_preview(client, other_user, simulation):
    client.force_login(other_user)
    assert client.post(_preview(simulation), post_data(simulation.get_params())).status_code == 404
    client.force_login(simulation.owner)
    assert client.get(_preview(simulation)).status_code == 405


# --- Sliders and the unsaved-changes guard -----------------------------------------------------------------------


def test_bounded_float_parameters_get_a_slider():
    specs = {spec.path: spec for spec in iter_fields(SimulationParams)}
    assert slider_step(specs["prefs.applicant_pref_correlation"]) == 0.01
    assert slider_step(specs["market.applicants_per_position"]) == 0.01
    assert slider_step(specs["rol.reservation_utility"]) == 0.1
    assert slider_step(specs["market.n_applicants"]) is None  # an integer
    assert slider_step(specs["invites.interviews_per_position"]) is None  # too wide for a slider
    field = ScalarForm.base_fields[form_name("prefs.applicant_pref_correlation")]
    assert field.widget.attrs["data-slider"] == 0.01


def test_the_parameter_form_guards_unsaved_changes(auth_client, simulation):
    body = auth_client.get(_manage(simulation)).content.decode()
    assert 'id="parameters" novalidate data-dirty-guard' in body
    assert "data-dirty-indicator hidden" in body
    assert 'data-slider="0.01"' in body
