"""Help pages: the public guide and the staff-only developer reference."""

import inspect
from types import ModuleType
from typing import Any

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_not_required
from django.db import models as db_models
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from . import models, params, pipeline, runs
from .engine import MODEL_VERSION, persistence, population, rank, rng, utility
from .engine import pipeline as engine_pipeline
from .limits import max_pairs
from .params import ParamField, SimulationParams, iter_fields, list_fields
from .params_forms import IMPLEMENTED_SECTIONS, SECTIONS, choice_label
from .population_csv import MAX_UPLOAD_BYTES, MAX_UPLOAD_ROWS, columns


def _value(value: Any) -> str:
    """Return a default value as text for the reference table."""
    if value is None:
        return "blank"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, str):
        return choice_label(value)
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _row(spec: ParamField) -> dict[str, Any]:
    """Describe one parameter for the reference table."""
    if spec.minimum is not None or spec.maximum is not None:
        low = "" if spec.minimum is None else f"{'>' if spec.exclusive_minimum else ''}{spec.minimum:g}"
        high = "" if spec.maximum is None else f"{spec.maximum:g}"
        limits = f"{low}\u2013{high}"  # en dash
    elif spec.choices:
        limits = ", ".join(choice_label(choice) for choice in spec.choices)
    else:
        limits = ""
    return {
        "path": spec.path,
        "title": spec.title,
        "description": spec.description,
        "unit": spec.unit,
        "limits": limits,
        "default": _value(spec.default) if not isinstance(spec.default, list | dict) else "",
        "implemented": spec.implemented,
    }


def parameter_sections() -> list[dict[str, Any]]:
    """Return the parameter reference, section by section, generated from the schema."""
    scalars = list(iter_fields(SimulationParams))
    lists = list(list_fields())
    sections = []
    for key in SECTIONS:
        field = SimulationParams.model_fields[key]
        rows = [_row(spec) for spec in scalars if spec.path.split(".")[0] == key]
        tables = [
            {
                "path": path,
                "title": list_field.title,
                "description": list_field.description,
                "columns": [_row(spec) for spec in iter_fields(item_model, implemented=key in IMPLEMENTED_SECTIONS)],
                "default": [item.model_dump() for item in list_field.get_default(call_default_factory=True)],
            }
            for path, list_field, item_model in lists
            if path.split(".")[0] == key
        ]
        sections.append(
            {
                "key": key,
                "title": field.title,
                "implemented": key in IMPLEMENTED_SECTIONS,
                "rows": rows,
                "tables": tables,
            }
        )
    return sections


@login_not_required
@require_GET
def help_index(request):
    """The user guide: quick start, the model, parameters, CSV formats and known limitations."""
    defaults = SimulationParams()
    context = {
        "sections": parameter_sections(),
        "csv_columns": {side: columns(defaults, side) for side in ("applicants", "programs")},
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        "max_upload_rows": MAX_UPLOAD_ROWS,
        "max_pairs": max_pairs(),
        "background": settings.TASK_BACKEND == "database",
        "model_version": MODEL_VERSION,
        "default_market": {
            "applicants": defaults.market.n_applicants,
            "positions": defaults.n_positions(),
            "programs": defaults.n_programs(),
        },
    }
    return render(request, "nrmps/help/index.html", context)


@login_not_required
@require_GET
def documentation_redirect(request):
    """The old /documentation/ page moved to the help guide."""
    return redirect("nrmps:help", permanent=True)


def _own_methods(cls: type) -> list[dict[str, str]]:
    """Public methods defined in the class body itself (not inherited from Django)."""
    return [
        {"name": name, "signature": str(inspect.signature(member)), "docstring": inspect.getdoc(member) or ""}
        for name, member in vars(cls).items()
        if not name.startswith("_") and inspect.isfunction(member)
    ]


def _module_functions(module: ModuleType) -> list[dict[str, str]]:
    """Public functions defined in `module`."""
    return [
        {
            "name": f"{module.__name__.removeprefix('nrmps.')}.{name}",
            "signature": str(inspect.signature(member)),
            "docstring": inspect.getdoc(member) or "",
        }
        for name, member in inspect.getmembers(module, inspect.isfunction)
        if not name.startswith("_") and member.__module__ == module.__name__
    ]


REFERENCE_MODELS = (
    models.Simulation,
    models.PopulationUpload,
    models.SimulationRun,
    models.StageRun,
    models.RunArtifact,
)
REFERENCE_MODULES = (runs, pipeline, params, engine_pipeline, population, utility, rank, rng, persistence)


@staff_member_required
@require_GET
def developer_reference(request):
    """Staff-only reference generated from the models, the run service and the engine docstrings."""
    model_rows = []
    for cls in REFERENCE_MODELS:
        fields = [
            {"name": f.name, "type": type(f).__name__, "help_text": getattr(f, "help_text", "")}
            for f in cls._meta.get_fields()
            if isinstance(f, db_models.Field)
        ]
        model_rows.append(
            {
                "name": cls.__name__,
                "verbose_name": cls._meta.verbose_name,
                "docstring": inspect.getdoc(cls) or "",
                "fields": fields,
                "methods": _own_methods(cls),
            }
        )
    functions = [function for module in REFERENCE_MODULES for function in _module_functions(module)]
    return render(request, "nrmps/help/developer.html", {"models": model_rows, "functions": functions})
