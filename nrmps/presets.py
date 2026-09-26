"""Parameter presets: named starting points for a simulation (plan steps 4.2 and 4.6).

Built-in presets list only what they change from the defaults (`SimulationParams()`); `preset_params` validates the
result and keeps the simulation's seed, so applying a preset never draws a new market by accident. Every built-in
preset is validated by the tests and fits within the default size limit, so it runs without a worker.

Users can also save a simulation's parameters as a preset of their own (`nrmps.models.SavedPreset`, stored without
the seed). `preset_options` lists both kinds for a user, and `resolve_preset` turns a choice into parameters: a
built-in preset's key, or "user:<id>" for a saved one.
"""

from dataclasses import dataclass, field
from typing import Any

from .params import SimulationParams, load_params

GOLD_SILVER = [{"name": "gold", "count": 3, "boost": 0.8}, {"name": "silver", "count": 5, "boost": 0.4}]


@dataclass(frozen=True)
class Preset:
    """A named set of parameter changes from the defaults."""

    title: str
    description: str
    changes: dict[str, Any] = field(default_factory=dict)


PRESETS: dict[str, Preset] = {
    "nrmp_like": Preset(
        "NRMP-like market",
        "The defaults: 1,000 applicants in NRMP-like groups for 926 positions in 142 programs (1.08 applicants per "
        "position), moderate agreement on both sides, and noisy views before interviews.",
    ),
    "classroom": Preset(
        "Small classroom market",
        "60 applicants and 8 programs: quick to run, and small enough to follow every applicant and program.",
        {"market": {"n_applicants": 60, "applicants_per_position": 1.2, "n_programs": 8}},
    ),
    "competitive": Preset(
        "Competitive specialty",
        "1.5 applicants per position and programs that agree on whom they want: many applicants go unmatched.",
        {"market": {"applicants_per_position": 1.5}, "prefs": {"program_pref_correlation": 0.85}},
    ),
    "more_positions": Preset(
        "More positions than applicants",
        "0.9 applicants per position: nearly every applicant matches and many positions stay unfilled.",
        {"market": {"applicants_per_position": 0.9}},
    ),
    "signals": Preset(
        "Preference signals",
        "Each applicant sends 3 gold and 5 silver signals to programs they apply to; 90% of programs read them "
        "when choosing whom to interview.",
        {"signals": {"tiers": GOLD_SILVER, "program_use_share": 0.9}},
    ),
    "perfect_information": Preset(
        "Perfect information",
        "No noise before or after interviews and no surprises at the interview: everyone ranks by their true "
        "preferences. A baseline for the effect of imperfect information.",
        {
            "info": {
                "applicant_pre_noise_sd": 0.0,
                "program_pre_noise_sd": 0.0,
                "interview_informativeness": 1.0,
                "fit_shock_sd": 0.0,
            }
        },
    ),
    "same_favourites": Preset(
        "Everyone wants the same programs",
        "High agreement on both sides (0.9): applicants want the same programs and programs the same applicants, "
        "so the top of the market is crowded.",
        {"prefs": {"applicant_pref_correlation": 0.9, "program_pref_correlation": 0.9}},
    ),
}
DEFAULT_PRESET = "nrmp_like"


def _merge(base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Return `base` with `changes` applied: nested groups are merged, anything else (lists too) replaced."""
    result = dict(base)
    for key, value in changes.items():
        result[key] = (
            _merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
        )
    return result


def preset_params(key: str, seed: int | None = None) -> SimulationParams:
    """Return the parameters of preset `key`, with `seed` as the run seed.

    Raises KeyError for an unknown preset.
    """
    data = _merge(SimulationParams().to_json_data(), PRESETS[key].changes)
    data["run"] = dict(data["run"]) | {"seed": seed}
    return load_params(data)


def preset_choices() -> list[tuple[str, str]]:
    """Return the presets as (key, title) choices."""
    return [(key, preset.title) for key, preset in PRESETS.items()]


USER_PREFIX = "user:"


@dataclass(frozen=True)
class PresetOption:
    """A preset a user can choose: built in or saved by the user."""

    key: str
    title: str
    description: str
    own: bool


def preset_options(user: Any) -> list[PresetOption]:
    """Return the built-in presets, then the user's saved presets by name."""
    options = [PresetOption(key, preset.title, preset.description, own=False) for key, preset in PRESETS.items()]
    if getattr(user, "is_authenticated", False):
        options += [
            PresetOption(f"{USER_PREFIX}{saved.pk}", saved.name, saved.description, own=True)
            for saved in user.presets.all()
        ]
    return options


def resolve_preset(user: Any, key: str, seed: int | None) -> tuple[str, SimulationParams]:
    """Return the title and parameters (with `seed`) of a preset option.

    Raises KeyError for an unknown option (or another user's preset), and pydantic's ValidationError for a saved
    preset that no longer fits the parameter schema.
    """
    if key in PRESETS:
        return PRESETS[key].title, preset_params(key, seed=seed)
    number = key.removeprefix(USER_PREFIX)
    if not key.startswith(USER_PREFIX) or not number.isdigit() or not getattr(user, "is_authenticated", False):
        raise KeyError(key)
    saved = user.presets.filter(pk=int(number)).first()
    if saved is None:
        raise KeyError(key)
    data = dict(saved.params)
    data["run"] = dict(data.get("run") or {}) | {"seed": seed}
    return saved.name, load_params(data)


def saved_params(params: SimulationParams) -> dict[str, Any]:
    """Return parameters as a saved preset stores them: the JSON without the seed."""
    return params.with_seed(None).to_json_data()
