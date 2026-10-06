"""Help pages: the public guide and the staff-only developer reference."""

import inspect
from types import ModuleType
from typing import Any

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_not_required
from django.db import models as db_models
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_safe

from . import models, params, pipeline, runs, validation
from .engine import (
    applications,
    interviews,
    invitations,
    match,
    outcomes,
    persistence,
    population,
    rank,
    rng,
    rol,
    signals,
    utility,
    validate,
)
from .engine import pipeline as engine_pipeline
from .guide import INDEX, apply_values, guide_pages, help_url_parts, render_page
from .help_registry import param_anchor, param_limits, param_value
from .help_search import MAX_RESULTS, search
from .params import ParamField, SimulationParams, iter_fields, list_fields
from .params_forms import IMPLEMENTED_SECTIONS, SECTIONS


def _row(spec: ParamField) -> dict[str, Any]:
    """Describe one parameter for the reference table."""
    return {
        "path": spec.path,
        "anchor": param_anchor(spec.path),
        "title": spec.title,
        "description": spec.description,
        "unit": spec.unit,
        "limits": param_limits(spec),
        "default": param_value(spec.default) if not isinstance(spec.default, list | dict) else "",
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
                "anchor": param_anchor(path),
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


def help_url(target: str) -> str:
    """Return the URL of a help target: a guide page's slug, optionally with "#anchor" (for example "model")."""
    slug, anchor = help_url_parts(target)
    url = reverse("nrmps:help") if slug == INDEX else reverse("nrmps:help_page", kwargs={"slug": slug})
    return f"{url}#{anchor}" if anchor else url


def _pages() -> list[dict[str, str]]:
    return [{"slug": page.slug, "title": page.title, "url": help_url(page.slug)} for page in guide_pages()]


def _guide_response(request, slug: str):
    try:
        rendered = render_page(slug)
    except KeyError as exc:
        raise Http404("No such help page") from exc
    context = {"rendered": rendered, "pages": _pages(), "summary": apply_values(rendered.page.summary)}
    return render(request, "nrmps/help/page.html", context)


MAX_QUERY = 100  # characters of a search query


@login_not_required
@require_safe
def help_search(request):
    """Search the help (plan step 5.1): the guide, the glossary, the parameters, the charts, columns and buttons."""
    query = " ".join(request.GET.get("q", "").split())[:MAX_QUERY]
    context = {"query": query, "results": search(query) if query else [], "pages": _pages(), "max_results": MAX_RESULTS}
    return render(request, "nrmps/help/search.html", context)


@login_not_required
@require_safe
def help_index(request):
    """The guide's home page: what the simulator does, a quick start, the guide's pages and the limitations."""
    return _guide_response(request, INDEX)


@login_not_required
@require_safe
def help_page(request, slug: str):
    """One page of the guide (nrmps/help_content/<slug>.md)."""
    if slug == INDEX:
        return redirect("nrmps:help", permanent=True)
    return _guide_response(request, slug)


@login_not_required
@require_safe
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
REFERENCE_MODULES = (
    runs,
    pipeline,
    params,
    engine_pipeline,
    population,
    utility,
    rank,
    rng,
    applications,
    signals,
    invitations,
    interviews,
    rol,
    match,
    outcomes,
    validate,
    validation,
    persistence,
)


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
