"""The typed parameter schema and its generated forms (plan step 2.1)."""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from nrmps.params import (
    MAX_PAIRS,
    STAGE_INPUTS,
    ApplicantAttribute,
    SimulationParams,
    iter_fields,
    list_fields,
    load_params,
    stage_inputs,
)
from nrmps.params_forms import LISTS, ParamsForm, form_name, post_data


def _errors(data: dict) -> list[tuple[tuple, str]]:
    with pytest.raises(ValidationError) as info:
        SimulationParams.model_validate(data)
    return [(error["loc"], error["type"]) for error in info.value.errors()]


# --- Defaults and derived values -----------------------------------------------------------------------------------


def test_defaults_are_valid_and_derive_the_spec_market():
    params = SimulationParams()
    assert params.market.n_applicants == 1000
    assert params.n_positions() == 926  # round(1000 / 1.08)
    assert params.n_programs() == 142  # round(926 / 6.5), model_spec.md §11
    assert params.warnings() == []


def test_explicit_program_count_wins():
    params = SimulationParams.model_validate({"market": {"n_programs": 50}})
    assert params.n_programs() == 50


def test_positions_round_half_to_even():
    # 1000 / 1.6 = 625 exactly; 25 / 2 = 12.5 rounds to 12.
    params = SimulationParams.model_validate({"market": {"n_applicants": 25, "applicants_per_position": 2.0}})
    assert params.n_positions() == 12


# --- Validation ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "loc", "kind"),
    [
        ({"run": {"seed": -1}}, ("run", "seed"), "greater_than_equal"),
        ({"run": {"seed": 2**63}}, ("run", "seed"), "less_than_equal"),
        ({"market": {"n_applicants": 5}}, ("market", "n_applicants"), "greater_than_equal"),
        ({"market": {"applicants_per_position": float("nan")}}, ("market", "applicants_per_position"), "finite_number"),
        ({"market": {"n_programs": 5000}}, ("market",), "value_error"),  # more programs than positions
        ({"prefs": {"unknown": 1}}, ("prefs", "unknown"), "extra_forbidden"),
        ({"applicants": {"groups": [{"name": "a", "share": 0.5}]}}, ("applicants", "groups"), "value_error"),
        (
            {"applicants": {"groups": [{"name": "Bad Name", "share": 1}]}},
            ("applicants", "groups", 0, "name"),
            "string_pattern_mismatch",
        ),
        ({"applicants": {"attributes": []}}, ("applicants", "attributes"), "too_short"),
        (
            {"programs": {"tiers": [{"name": "top", "share": 0.3}, {"name": "rest", "share": 0.6}]}},
            ("programs", "tiers"),
            "value_error",
        ),
        ({"programs": {"quality_sd": 0}}, ("programs", "quality_sd"), "greater_than"),
        ({"schema_version": 2}, ("schema_version",), "literal_error"),
    ],
)
def test_invalid_parameters_are_rejected_where_they_are(data, loc, kind):
    assert (loc, kind) in _errors(data)


def test_duplicate_names_and_keys_are_rejected():
    attribute = {"key": "research", "program_weight_prior": 1}
    assert (("applicants", "attributes"), "value_error") in _errors({"applicants": {"attributes": [attribute] * 2}})
    group = {"name": "md", "share": 0.5}
    assert (("applicants", "groups"), "value_error") in _errors({"applicants": {"groups": [group, group]}})


def test_pair_limit():
    # 60,000 applicants x 1,000 programs = 6e7 pairs, above the model's limit of 5e7.
    assert MAX_PAIRS < 60_000 * 1000
    assert (("market",), "value_error") in _errors({"market": {"n_applicants": 60_000, "n_programs": 1000}})


def test_shares_may_be_off_by_rounding():
    shares = [1 / 3, 1 / 3, 1 / 3]
    groups = [{"name": f"g{i}", "share": share} for i, share in enumerate(shares)]
    SimulationParams.model_validate({"applicants": {"groups": groups}})


def test_integers_become_floats_so_hashes_do_not_depend_on_how_a_number_was_typed():
    a = SimulationParams.model_validate({"prefs": {"taste_share": 1}})
    b = SimulationParams.model_validate({"prefs": {"taste_share": 1.0}})
    assert isinstance(a.prefs.taste_share, float)
    assert a.params_hash() == b.params_hash()


# --- Warnings --------------------------------------------------------------------------------------------------------


def test_warnings_for_unusual_or_planned_settings():
    params = SimulationParams.model_validate(
        {
            "market": {"applicants_per_position": 2.5},
            "programs": {"attributes": [{"key": "reputation", "applicant_weight_prior": 1}]},
            "invites": {"screen_attribute": "step_2"},
        }
    )
    paths = {warning.path for warning in params.warnings()}
    # 2.5 applicants per position also leaves 4 interview slots per applicant, under half the cap of 12.
    assert paths == {
        "market.applicants_per_position",
        "programs.attributes",
        "invites.screen_attribute",
        "invites.interviews_per_position",
    }


# --- Serialisation, loading and stage inputs ---------------------------------------------------------------------


def test_json_round_trip_and_stable_hash():
    params = SimulationParams.model_validate({"run": {"seed": 42}, "market": {"n_applicants": 300}})
    again = load_params(json.loads(json.dumps(params.to_json_data())))
    assert again == params
    assert again.params_hash() == params.params_hash()
    assert len(params.params_hash()) == 64


def test_load_params_fills_defaults():
    assert load_params(None) == SimulationParams()
    assert load_params({"schema_version": 1, "market": {"n_applicants": 50}}).market.n_applicants == 50


def test_implemented_data_leaves_out_planned_parameters():
    data = SimulationParams().implemented_data()
    assert set(data["run"]) == {"seed"}
    assert set(data["interview"]) == {"applicant_cap", "acceptance_order"}
    assert "fit_shock_sd" in data["info"]
    assert "applications_mean" in data["applicants"]["groups"][0]


def test_stage_inputs_change_only_with_what_the_stage_reads():
    base = SimulationParams()
    noisier = SimulationParams.model_validate({"info": {"applicant_pre_noise_sd": 1.0}})
    bigger = SimulationParams.model_validate({"market": {"n_applicants": 2000}})
    planned = SimulationParams.model_validate({"apps": {"mean": 40}, "run": {"replicates": 5}})
    assert stage_inputs(noisier, "population") == stage_inputs(base, "population")
    assert stage_inputs(noisier, "pre_interview") != stage_inputs(base, "pre_interview")
    assert stage_inputs(bigger, "population") != stage_inputs(base, "population")
    for stage in ("population", "pre_interview"):
        assert stage_inputs(planned, stage) == stage_inputs(base, stage)


def test_every_parameter_is_described():
    for spec in iter_fields(SimulationParams):
        assert spec.title, spec.path
        assert spec.description, spec.path
    for path, _field, item_model in list_fields():
        for spec in iter_fields(item_model):
            assert spec.title, f"{path}.{spec.path}"
            assert spec.description, f"{path}.{spec.path}"


def test_planned_parameters_are_marked():
    planned = {spec.path for spec in iter_fields(SimulationParams) if not spec.implemented}
    assert planned == {
        "run.replicates",
        "run.resample_population",
        "run.ci_level",
        "interview.n_dates",
        "interview.dates_per_program",
    }


def test_each_stage_reads_only_its_own_parameters():
    base = SimulationParams()
    changes = {
        "applications": {"apps": {"mean": 12}},
        "signals": {"signals": {"allocation": "random"}},
        "invitations": {"invites": {"rounds": 5}},
        "interviews": {"info": {"fit_shock_sd": 0.9}},
        "rank_lists": {"rol": {"applicant_top_k": 3}},
        "match": {"match": {"compare_both": True}},
    }
    for changed_stage, groups in changes.items():
        other = SimulationParams.model_validate(groups)
        for stage in STAGE_INPUTS:
            same = stage_inputs(other, stage) == stage_inputs(base, stage)
            assert same == (stage != changed_stage), (changed_stage, stage)
    # A group's application mean belongs to the applications stage, not to the population.
    groups = [g.model_dump() | {"applications_mean": 50.0} for g in base.applicants.groups]
    other = SimulationParams.model_validate({"applicants": {"groups": groups}})
    assert stage_inputs(other, "population") == stage_inputs(base, "population")
    assert stage_inputs(other, "applications") != stage_inputs(base, "applications")


# --- Forms ------------------------------------------------------------------------------------------------------------


def _form(params: SimulationParams, **changes: str) -> ParamsForm:
    data = post_data(params) | changes
    return ParamsForm(data, initial=params)


def test_form_round_trip_gives_the_same_parameters():
    params = SimulationParams.model_validate({"run": {"seed": 7}, "programs": {"tiers": [{"name": "top", "share": 1}]}})
    form = _form(params)
    assert form.is_valid(), form.error_summary()
    assert form.params == params


def test_form_field_errors_come_from_the_schema_limits():
    form = _form(SimulationParams(), market__n_applicants="5")
    assert not form.is_valid()
    assert "market__n_applicants" in form.scalars.errors


def test_form_cell_errors_land_in_the_right_row():
    form = _form(SimulationParams(), **{"applicants__groups-2-name": "US IMG"})
    assert not form.is_valid()
    rows = form.formsets["applicants.groups"].forms
    assert "name" in rows[2].errors
    assert not rows[0].errors


def test_form_list_errors_and_section_errors():
    form = _form(SimulationParams(), **{"applicants__groups-0-share": "0.5"})
    assert not form.is_valid()
    assert form.section_errors["applicants.groups"] == ["The group shares add up to 1.06; they must add up to 1."]
    form = _form(SimulationParams(), market__n_programs="5000")
    assert not form.is_valid()
    assert form.section_errors["market"][0].startswith("5,000 programs need at least 5,000 positions")
    assert any(label == "Market" for _anchor, label, _message in form.error_summary())


def test_form_rows_can_be_deleted_but_not_all():
    params = SimulationParams()
    form = _form(params, **{"applicants__attributes-1-DELETE": "on"})
    assert form.is_valid(), form.error_summary()
    assert [a.key for a in form.params.applicants.attributes] == ["board_scores", "honors"]
    deletes = {f"programs__attributes-{i}-DELETE": "on" for i in range(3)}
    form = _form(params, **deletes)
    assert not form.is_valid()
    assert form.section_errors["programs.attributes"]


def test_form_rows_can_be_added():
    params = SimulationParams()
    prefix = form_name("programs.attributes")
    data = post_data(params) | {
        f"{prefix}-TOTAL_FORMS": "4",
        f"{prefix}-3-key": "rural",
        f"{prefix}-3-corr_with_quality": "0",
        f"{prefix}-3-applicant_weight_prior": "0.1",
    }
    form = ParamsForm(data, initial=params)
    assert form.is_valid(), form.error_summary()
    assert form.params.programs.attributes[-1].key == "rural"


def test_form_sections_separate_planned_parameters():
    form = ParamsForm()
    implemented = {bound.name for section in form.sections() for bound in section.fields + section.advanced_fields}
    planned = {bound.name for section in form.sections(planned=True) for bound in section.fields}
    assert "info__applicant_pre_noise_sd" in implemented
    assert "info__fit_shock_sd" in implemented
    assert "interview__n_dates" in planned
    assert not implemented & planned
    lists = {view.spec.path for section in form.sections() for view in section.lists}
    assert lists == {
        "applicants.groups",
        "applicants.attributes",
        "programs.tiers",
        "programs.attributes",
        "signals.tiers",
    }
    assert LISTS["signals.tiers"].implemented


@settings(max_examples=40, deadline=None)
@given(
    seed=st.none() | st.integers(0, 2**63 - 1),
    n=st.integers(10, 5000),
    ratio=st.floats(0.5, 3.0),
    rho=st.floats(0, 1),
    noise=st.floats(0, 3),
    corr=st.floats(0, 1),
    prior=st.floats(0.001, 100),
)
def test_any_valid_parameters_survive_the_form(seed, n, ratio, rho, noise, corr, prior):
    params = SimulationParams.model_validate(
        {
            "run": {"seed": seed},
            "market": {"n_applicants": n, "applicants_per_position": ratio},
            "prefs": {"applicant_pref_correlation": rho},
            "info": {"program_pre_noise_sd": noise},
            "applicants": {
                "attributes": [ApplicantAttribute(key="step_1", corr_with_strength=corr, program_weight_prior=prior)]
            },
        }
    )
    form = _form(params)
    assert form.is_valid(), form.error_summary()
    assert form.params == params
