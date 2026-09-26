"""Template tags for rendering form fields with daisyUI 5 markup."""

import copy

from django import template
from django.forms import widgets

from nrmps.help_registry import param_anchor, param_limits, param_value

register = template.Library()

# daisyUI 5 component class for each widget type; each also has an "-error" variant.
WIDGET_CLASSES: list[tuple[type[widgets.Widget], str]] = [
    (widgets.CheckboxInput, "checkbox"),
    (widgets.Textarea, "textarea"),
    (widgets.Select, "select"),
    (widgets.FileInput, "file-input"),
    (widgets.Input, "input"),
]


def widget_class(widget: widgets.Widget, *, invalid: bool) -> str:
    """Return the daisyUI classes for a widget, with the error variant when the field is invalid."""
    for widget_type, name in WIDGET_CLASSES:
        if isinstance(widget, widget_type):
            classes = [name] if name == "checkbox" else [name, "w-full"]
            if invalid:
                classes.append(f"{name}-error")
            return " ".join(classes)
    return ""


@register.inclusion_tag("nrmps/components/field.html")
def field_row(field, label: str | None = None):
    """Render a bound field as a fieldset: label, widget, help text and errors.

    The help text and error elements get the ids that Django's `aria-describedby` on the widget points to
    (`<id>_helptext`, `<id>_error`), so screen readers announce them with the input.
    """
    widget = field.field.widget
    attrs = {"class": widget_class(widget, invalid=bool(field.errors))}
    existing = widget.attrs.get("class")
    if existing:
        attrs["class"] = f"{attrs['class']} {existing}"
    return {
        "field": field,
        "label": label or field.label,
        "widget_html": field.as_widget(attrs=attrs),
        "is_checkbox": isinstance(widget, widgets.CheckboxInput),
        # Forms list parameters the engine does not use yet in `planned_fields`.
        "planned": field.name in getattr(field.form, "planned_fields", ()),
        "facts": _parameter_facts(field),
    }


def _parameter_facts(field) -> dict[str, str] | None:
    """Return a schema parameter's range, unit, default and help anchor (None for fields of other forms)."""
    spec = getattr(field.form, "specs", {}).get(field.name)
    if spec is None:
        return None
    default = "" if isinstance(spec.default, list | dict) else param_value(spec.default)
    limits = param_limits(spec)
    return {
        "range": "" if spec.choices else limits,
        "unit": spec.unit,
        "default": default,
        "anchor": param_anchor(spec.path),
    }


@register.inclusion_tag("nrmps/components/cell.html")
def cell(field, row: int | str = "", described_by: str = ""):
    """Render a bound field as a compact table cell input, labelled for screen readers by column and row.

    Used by the list editors (formsets) of the parameter form, where the column header is the visible label. `row` is
    the row number, or a word such as "new row"; `described_by` is the id of the list's description (cells do not
    repeat the help text, so they must not point at a help element of their own).
    """
    row = f"row {row}" if isinstance(row, int) else str(row)
    widget = field.field.widget
    is_checkbox = isinstance(widget, widgets.CheckboxInput)
    classes = "checkbox checkbox-sm" if is_checkbox else widget_class(widget, invalid=bool(field.errors))
    if not is_checkbox:
        classes = classes.replace("w-full", "") + (" input-sm w-28" if "input" in classes else " select-sm w-36")
    label = f"{field.label}, {row}" if row else str(field.label)
    attrs = {"class": classes.strip(), "aria-label": label}
    references = [described_by] if described_by else []
    if field.errors:
        attrs["aria-invalid"] = "true"
        references.append(f"{field.auto_id}_error")
    if references:
        attrs["aria-describedby"] = " ".join(references)
    elif field.help_text:
        field = _without_help(field)
    return {"field": field, "widget_html": field.as_widget(attrs=attrs)}


def _without_help(field):
    """Return the bound field with its help text removed, so Django adds no aria-describedby for it."""
    field.field = copy.copy(field.field)
    field.field.help_text = ""
    return field
