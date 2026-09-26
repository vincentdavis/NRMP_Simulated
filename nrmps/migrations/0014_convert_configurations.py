# Plan step 2.3 and decision D3: convert each simulation's latest configuration to model 2.0 parameters where a
# field has an equivalent (market size and tightness, attribute names); everything else takes the model's defaults.
# The legacy populations and interview rows are not converted: they were produced by the pre-fix model.

import re
import secrets

from django.db import migrations

APPLICANT_ATTRIBUTES = {"board_scores": (0.8, 0.5), "research": (0.5, 0.3), "honors": (0.6, 0.2)}
PROGRAM_ATTRIBUTES = {"reputation": (0.9, 0.5), "program_size": (0.0, 0.2), "location": (0.0, 0.3)}


def _key(name) -> str:
    """Turn a legacy attribute name into a model 2.0 key (lowercase, starting with a letter, at most 40 characters)."""
    key = re.sub(r"[^a-z0-9_]", "_", str(name).lower())
    if not key[:1].isalpha():
        key = f"a_{key}"
    return key[:40]


def _attributes(names, defaults, corr_field, weight_field):
    result, seen = [], set()
    for name in names if isinstance(names, list) else []:
        key = _key(name)
        if key in seen:
            continue
        seen.add(key)
        corr, weight = defaults.get(key, (0.5, 0.2))
        result.append({"key": key, corr_field: corr, weight_field: weight})
    return result[:10]


def _params(config, seed: int) -> dict:
    fallback = {"schema_version": 1, "run": {"seed": seed}}
    if config is None:
        return fallback
    n = min(max(int(config.number_of_applicants), 10), 60_000)
    programs = max(1, int(config.number_of_schools))
    size = min(max(float(config.school_capacity_mean), 1.0), 60.0)
    ratio = round(min(max(n / (programs * size), 0.5), 3.0), 4)
    market = {"n_applicants": n, "applicants_per_position": ratio, "program_size_mean": size}
    if programs <= max(1, round(n / ratio)) and n * programs <= 50_000_000:
        market["n_programs"] = programs
    data = {**fallback, "market": market}
    if applicant := _attributes(config.school_meta_preference, APPLICANT_ATTRIBUTES, "corr_with_strength", "program_weight_prior"):
        data["applicants"] = {"attributes": applicant}
    if program := _attributes(config.applicant_meta_preference, PROGRAM_ATTRIBUTES, "corr_with_quality", "applicant_weight_prior"):
        data["programs"] = {"attributes": program}
    # Check the result with the schema of this release (later schema versions upgrade stored parameters on load); if
    # anything does not fit, keep only the seed and let the defaults apply.
    from nrmps.params import load_params

    try:
        return load_params(data).to_json_data()
    except ValueError:
        return fallback


def convert(apps, schema_editor):
    Simulation = apps.get_model("nrmps", "Simulation")
    SimulationConfig = apps.get_model("nrmps", "SimulationConfig")
    for simulation in Simulation.objects.all().iterator():
        config = SimulationConfig.objects.filter(simulation=simulation).order_by("-id").first()
        simulation.params = _params(config, secrets.randbelow(10**9))
        simulation.save(update_fields=["params"])


class Migration(migrations.Migration):

    dependencies = [
        ("nrmps", "0013_simulation_params"),
    ]

    operations = [
        migrations.RunPython(convert, migrations.RunPython.noop),
    ]
