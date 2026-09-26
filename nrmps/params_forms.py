"""Django forms generated from the parameter schema (`nrmps.params`).

`ParamsForm` renders every scalar parameter as a form field named by its dotted path with `__` instead of dots
(`market__n_applicants`) and every list of groups (applicant groups, attributes, tiers) as a formset with the same
kind of prefix (`applicants__groups`). Validation runs in two passes: Django checks each value's type and range, then
pydantic checks the assembled parameters, and its errors are attached to the field, the table cell or the section
they concern. Nothing about a parameter is written twice: labels, help, limits and defaults all come from the schema.
"""

import types
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, ClassVar

from django import forms
from django.core.validators import RegexValidator
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from pydantic_core import ErrorDetails, PydanticUndefined

from .params import KEY_HELP, ParamField, SimulationParams, iter_fields, list_fields

SEP = "__"

# Labels for enum values that do not read well with underscores replaced by spaces.
CHOICE_LABELS = {
    "negbin": "Negative binomial",
    "top_n": "Top n",
    "dnr_quantile": "Do-not-rank quantile",
    "dnr_threshold": "Do-not-rank threshold",
    "truncate_k": "Truncate to k",
    "top_k": "Top k",
}


def form_name(path: str) -> str:
    """Return the form field name (or formset prefix) of a dotted parameter path."""
    return path.replace(".", SEP)


def choice_label(value: str) -> str:
    """Return the display label of an enum value."""
    return CHOICE_LABELS.get(value, value.replace("_", " ").capitalize())


def _base_type(annotation: Any) -> tuple[Any, bool]:
    """Return (the type without None, whether None is allowed) for a field annotation."""
    if isinstance(annotation, types.UnionType):
        args = [arg for arg in annotation.__args__ if arg is not type(None)]
        return args[0], len(args) < len(annotation.__args__)
    return annotation, False


def make_field(spec: ParamField) -> forms.Field:
    """Build the Django form field for one scalar parameter."""
    base, optional = _base_type(spec.field.annotation)
    options: dict[str, Any] = {"label": spec.title, "help_text": spec.description, "required": not optional}
    if spec.default is not None and spec.default is not PydanticUndefined and not isinstance(spec.default, list | dict):
        # New rows of the list editors start from the schema defaults.
        options["initial"] = spec.default
    if spec.choices:
        return forms.TypedChoiceField(choices=[(c, choice_label(c)) for c in spec.choices], **options)
    if base is bool:
        options["required"] = False
        return forms.BooleanField(**options)
    if base is int:
        int_min = None if spec.minimum is None else int(spec.minimum) + (1 if spec.exclusive_minimum else 0)
        int_max = None if spec.maximum is None else int(spec.maximum)
        return forms.IntegerField(min_value=int_min, max_value=int_max, **options)
    if base is float:
        # An exclusive minimum (for example "greater than 0") is left to pydantic; the browser still gets `min`.
        float_min = None if spec.exclusive_minimum else spec.minimum
        float_field = forms.FloatField(min_value=float_min, max_value=spec.maximum, **options)
        float_field.widget.attrs["step"] = "any"
        if spec.exclusive_minimum and spec.minimum is not None:
            float_field.widget.attrs["min"] = spec.minimum
        return float_field
    if base is str:
        validators = [
            RegexValidator(pattern, message=f"Use {KEY_HELP}.")
            for pattern in (getattr(constraint, "pattern", None) for constraint in spec.field.metadata)
            if pattern
        ]
        return forms.CharField(
            max_length=40, empty_value=None if optional else "", strip=True, validators=validators, **options
        )
    raise TypeError(f"No form field for {spec.path} ({spec.field.annotation!r})")


class SchemaForm(forms.Form):
    """A form generated from a parameter model: `specs` describes each field, `planned_fields` get a badge."""

    specs: ClassVar[dict[str, ParamField]] = {}
    planned_fields: ClassVar[tuple[str, ...]] = ()


def _form_class(name: str, model: type[BaseModel]) -> type[SchemaForm]:
    """Return a SchemaForm class with one field per scalar parameter of `model`."""
    specs = list(iter_fields(model))
    attrs: dict[str, Any] = {form_name(spec.path): make_field(spec) for spec in specs}
    attrs["planned_fields"] = tuple(form_name(spec.path) for spec in specs if not spec.implemented)
    attrs["specs"] = {form_name(spec.path): spec for spec in specs}
    return type(name, (SchemaForm,), attrs)


ScalarForm = _form_class("ScalarForm", SimulationParams)


class ParamsFormSet(forms.BaseFormSet):
    """A formset for a list of parameter groups; its delete checkbox is labelled "Remove"."""

    def add_fields(self, form: forms.Form, index: int | None) -> None:
        """Add the delete checkbox with the label the table header uses."""
        super().add_fields(form, index)
        if "DELETE" in form.fields:
            form.fields["DELETE"].label = "Remove"


@dataclass
class ListSpec:
    """A list-of-groups parameter: its path, schema field and the formset class that edits it."""

    path: str
    title: str
    description: str
    implemented: bool
    level: str
    item_model: type[BaseModel]
    formset_class: type[forms.BaseFormSet]
    columns: list[ParamField]


def _list_specs() -> dict[str, ListSpec]:
    specs = {}
    for path, schema_field, item_model in list_fields():
        extra = schema_field.json_schema_extra if isinstance(schema_field.json_schema_extra, dict) else {}
        # Items in a planned group (signal tiers) are planned too.
        implemented = extra.get("implemented", True) is not False and path.split(".")[0] in IMPLEMENTED_SECTIONS
        max_length = next((m.max_length for m in schema_field.metadata if hasattr(m, "max_length")), 10)
        item_form = _form_class(f"{item_model.__name__}Form", item_model)
        formset_class = forms.formset_factory(
            item_form,
            formset=ParamsFormSet,
            extra=0,
            can_delete=True,
            max_num=max_length,
            absolute_max=max_length + 5,
        )
        specs[path] = ListSpec(
            path=path,
            title=schema_field.title or path,
            description=schema_field.description or "",
            implemented=implemented,
            level=str(extra.get("level", "basic")),
            item_model=item_model,
            formset_class=formset_class,
            columns=list(iter_fields(item_model)),
        )
    return specs


# The top-level groups, in page order, and which of them the engine implements.
SECTIONS = (
    "run",
    "market",
    "applicants",
    "programs",
    "prefs",
    "info",
    "apps",
    "signals",
    "invites",
    "interview",
    "rol",
    "match",
)
IMPLEMENTED_SECTIONS = tuple(
    key
    for key in SECTIONS
    if not isinstance(extra := SimulationParams.model_fields[key].json_schema_extra, dict)
    or extra.get("implemented", True) is not False
)
LISTS = _list_specs()


def _get(data: Any, path: str) -> Any:
    for part in path.split("."):
        data = getattr(data, part) if isinstance(data, BaseModel) else data[part]
    return data


def _set(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        data = data.setdefault(part, {})
    data[parts[-1]] = value


def _message(error: ErrorDetails) -> str:
    """Return a pydantic error's message without pydantic's "Value error, " prefix."""
    context = error.get("ctx") or {}
    if error["type"] == "value_error" and "error" in context:
        return str(context["error"])
    return str(error["msg"])


@dataclass
class Section:
    """One group of parameters on the page: its scalar fields, lists and errors."""

    key: str
    title: str
    description: str
    fields: list[forms.BoundField] = field(default_factory=list)
    advanced_fields: list[forms.BoundField] = field(default_factory=list)
    lists: list[FormsetView] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_advanced_errors(self) -> bool:
        """Return True if an advanced field has an error (its group is then shown open)."""
        return any(bound.errors for bound in self.advanced_fields)

    @property
    def has_errors(self) -> bool:
        """Return True if anything in the section has an error."""
        return bool(
            self.errors
            or any(bound.errors for bound in self.fields + self.advanced_fields)
            or any(view.errors or view.formset.total_error_count() for view in self.lists)
        )


@dataclass
class FormsetView:
    """A formset with its column descriptions, for the table editor."""

    spec: ListSpec
    formset: forms.BaseFormSet
    errors: list[str]

    @property
    def prefix(self) -> str:
        """Return the formset prefix (for the add-row script)."""
        return self.formset.prefix or ""


class ParamsForm:
    """The parameter editor: one form for the scalar parameters and one formset per list of groups.

    `is_valid()` validates both passes; afterwards `params` holds the validated `SimulationParams`. Errors that
    concern a whole group (for example shares that do not add up to 1) are in `section_errors[<group path>]`.
    """

    def __init__(self, data: Any = None, *, initial: SimulationParams | None = None):
        initial = initial or SimulationParams()
        self.initial_params = initial
        scalar_initial = {name: _get(initial, spec.path) for name, spec in ScalarForm.specs.items()}
        self.scalars = ScalarForm(data, initial=scalar_initial)
        self.formsets: dict[str, forms.BaseFormSet] = {}
        for path, spec in LISTS.items():
            rows = [item.model_dump() for item in _get(initial, path)]
            self.formsets[path] = spec.formset_class(data, initial=rows, prefix=form_name(path))
        self.section_errors: dict[str, list[str]] = defaultdict(list)
        self.params: SimulationParams | None = None
        self._kept: dict[str, list[forms.Form]] = {}

    @property
    def is_bound(self) -> bool:
        """Return True if the form was given submitted data."""
        return self.scalars.is_bound

    def is_valid(self) -> bool:
        """Validate the fields, then the assembled parameters; return True if both passed."""
        results = [self.scalars.is_valid(), *(formset.is_valid() for formset in self.formsets.values())]
        if not all(results):
            return False
        data: dict[str, Any] = {"schema_version": 1}
        for name, spec in ScalarForm.specs.items():
            _set(data, spec.path, self.scalars.cleaned_data[name])
        for path, formset in self.formsets.items():
            kept = [form for form in formset.forms if form.cleaned_data and not form.cleaned_data.get("DELETE")]
            self._kept[path] = kept
            _set(data, path, [{k: v for k, v in form.cleaned_data.items() if k != "DELETE"} for form in kept])
        try:
            self.params = SimulationParams.model_validate(data)
        except PydanticValidationError as exc:
            self._attach_errors(exc)
            return False
        return True

    def _attach_errors(self, exc: PydanticValidationError) -> None:
        """Attach each pydantic error to its field, table cell, list or section."""
        for error in exc.errors():
            loc = [str(part) for part in error["loc"]]
            message = _message(error)
            for depth in range(len(loc), 0, -1):
                path = ".".join(loc[:depth])
                if path in LISTS:
                    rest = loc[depth:]
                    kept = self._kept.get(path, [])
                    if len(rest) >= 2 and rest[0].isdigit() and int(rest[0]) < len(kept):
                        form = kept[int(rest[0])]
                        name = form_name(rest[1])
                        if name in form.fields:
                            form.add_error(name, message)
                            break
                    self.section_errors[path].append(message)
                    break
                name = form_name(path)
                if name in self.scalars.fields:
                    self.scalars.add_error(name, message)
                    break
            else:
                self.section_errors[loc[0] if loc else ""].append(message)

    @property
    def has_errors(self) -> bool:
        """Return True if any field, cell, list or section has an error (after `is_valid()`)."""
        return bool(
            self.scalars.errors
            or any(formset.total_error_count() for formset in self.formsets.values())
            or any(self.section_errors.values())
        )

    def error_summary(self) -> list[tuple[str, str, str]]:
        """Return (anchor id, label, message) for every error, for the summary at the top of the form."""
        summary = []
        for name, errors in self.scalars.errors.items():
            if name in self.scalars.fields:
                bound = self.scalars[name]
                summary.append((bound.id_for_label, str(bound.label), str(errors[0])))
            else:
                summary.append(("", "Parameters", str(errors[0])))
        for path, formset in self.formsets.items():
            spec = LISTS[path]
            for index, form in enumerate(formset.forms, start=1):
                for name, errors in form.errors.items():
                    label = str(form.fields[name].label) if name in form.fields else ""
                    anchor = form[name].id_for_label if name in form.fields else f"list-{formset.prefix}"
                    summary.append((anchor, f"{spec.title}, row {index}, {label}".rstrip(", "), str(errors[0])))
            summary.extend((f"list-{formset.prefix}", spec.title, str(error)) for error in formset.non_form_errors())
        for path, messages in self.section_errors.items():
            anchor = f"list-{form_name(path)}" if path in LISTS else f"section-{path or 'params'}"
            title = LISTS[path].title if path in LISTS else _section_title(path.split(".")[0]) if path else "Parameters"
            summary.extend((anchor, title, message) for message in messages)
        return summary

    @property
    def planned_sections(self) -> list[Section]:
        """Return the sections of parameters the engine does not use yet."""
        return self.sections(planned=True)

    @property
    def planned_has_errors(self) -> bool:
        """Return True if a planned parameter has an error (the planned group is then shown open)."""
        return any(section.has_errors for section in self.planned_sections)

    def sections(self, planned: bool = False) -> list[Section]:
        """Return the page sections: implemented parameters, or (planned=True) the ones not used yet."""
        result = []
        for key in SECTIONS:
            section = Section(key=key, title=_section_title(key), description=_section_description(key))
            for name, spec in ScalarForm.specs.items():
                if spec.path.split(".")[0] != key or spec.implemented == planned:
                    continue
                target = section.advanced_fields if spec.level == "advanced" and not planned else section.fields
                target.append(self.scalars[name])
            for path, list_spec in LISTS.items():
                if path.split(".")[0] == key and list_spec.implemented != planned:
                    errors = list(self.section_errors.get(path, []))
                    section.lists.append(FormsetView(list_spec, self.formsets[path], errors))
            if not planned:
                section.errors = list(self.section_errors.get(key, []))
            if section.fields or section.advanced_fields or section.lists or section.errors:
                result.append(section)
        return result


def _section_title(key: str) -> str:
    return str(SimulationParams.model_fields[key].title) if key in SimulationParams.model_fields else key


def _section_description(key: str) -> str:
    return str(SimulationParams.model_fields[key].description or "") if key in SimulationParams.model_fields else ""


def _post_value(value: Any) -> str | None:
    """Return a value as a browser would submit it; None for an unchecked checkbox (not submitted)."""
    if isinstance(value, bool):
        return "on" if value else None
    return "" if value is None else str(value)


def post_data(params: SimulationParams) -> dict[str, str]:
    """Return the POST data a browser would submit for `params` (for tests and scripted clients)."""
    data: dict[str, str] = {}
    for name, spec in ScalarForm.specs.items():
        if (value := _post_value(_get(params, spec.path))) is not None:
            data[name] = value
    for path, list_spec in LISTS.items():
        prefix = form_name(path)
        items = _get(params, path)
        management = {"TOTAL_FORMS": len(items), "INITIAL_FORMS": len(items), "MIN_NUM_FORMS": 0, "MAX_NUM_FORMS": 1000}
        data.update({f"{prefix}-{key}": str(count) for key, count in management.items()})
        for index, item in enumerate(items):
            for column in list_spec.columns:
                if (value := _post_value(_get(item, column.path))) is not None:
                    data[f"{prefix}-{index}-{form_name(column.path)}"] = value
    return data
