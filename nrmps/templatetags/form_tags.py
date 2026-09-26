"""Template tags for rendering form fields with daisyUI 5 markup."""

from django import template
from django.forms import widgets

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
    }
