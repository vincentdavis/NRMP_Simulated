"""Help pages: the public guide and the staff-only developer reference."""

import inspect

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_not_required
from django.db import models as db_models
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from . import models, simulation_engine
from .forms import SimulationConfigForm, SimulationForm
from .models import SimulationConfig
from .population_csv import COLUMNS, MAX_UPLOAD_BYTES, MAX_UPLOAD_ROWS


def _parameter_rows(form_class, model) -> list[dict]:
    """Describe each field of a form: label, help, limits, default and whether the engine uses it yet."""
    form = form_class()
    planned = getattr(form_class, "planned_fields", ())
    rows = []
    for name, field in form.fields.items():
        model_field = model._meta.get_field(name)
        default = model_field.get_default()
        rows.append(
            {
                "name": name,
                "label": field.label,
                "help": field.help_text,
                "min": field.widget.attrs.get("min"),
                "max": field.widget.attrs.get("max"),
                "default": ", ".join(default) if isinstance(default, list) else default,
                "planned": name in planned,
            }
        )
    return rows


@login_not_required
@require_GET
def help_index(request):
    """The user guide: quick start, the model, parameters, CSV formats and known limitations."""
    context = {
        "config_parameters": _parameter_rows(SimulationConfigForm, SimulationConfig),
        "simulation_parameters": _parameter_rows(SimulationForm, models.Simulation),
        "csv_columns": {"applicants": COLUMNS["students"], "programs": COLUMNS["schools"]},
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        "max_upload_rows": MAX_UPLOAD_ROWS,
        "max_pairs": settings.NRMP_MAX_PAIRS,
    }
    return render(request, "nrmps/help/index.html", context)


@login_not_required
@require_GET
def documentation_redirect(request):
    """The old /documentation/ page moved to the help guide."""
    return redirect("nrmps:help", permanent=True)


def _own_methods(cls) -> list[dict]:
    """Public methods defined in the class body itself (not inherited from Django)."""
    return [
        {"name": name, "signature": str(inspect.signature(member)), "docstring": inspect.getdoc(member) or ""}
        for name, member in vars(cls).items()
        if not name.startswith("_") and inspect.isfunction(member)
    ]


def _module_functions(module) -> list[dict]:
    """Public functions defined in `module`."""
    return [
        {
            "name": f"{module.__name__.rsplit('.', 1)[-1]}.{name}",
            "signature": str(inspect.signature(member)),
            "docstring": inspect.getdoc(member) or "",
        }
        for name, member in inspect.getmembers(module, inspect.isfunction)
        if not name.startswith("_") and member.__module__ == module.__name__
    ]


@staff_member_required
@require_GET
def developer_reference(request):
    """Staff-only reference generated from the simulation models and engine docstrings."""
    model_rows = []
    for cls in (models.Simulation, models.SimulationConfig, models.Student, models.School, models.Interview):
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
    functions = _module_functions(simulation_engine)
    return render(request, "nrmps/help/developer.html", {"models": model_rows, "functions": functions})
