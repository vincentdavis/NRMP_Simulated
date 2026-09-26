"""Validators shared by models and forms."""

import re

from django.core.exceptions import ValidationError

ATTRIBUTE_NAME_PATTERN = re.compile(r"^[a-z0-9_]{1,40}$")
MAX_ATTRIBUTES = 10


def validate_attribute_list(value) -> None:
    """Require a list of 1-10 unique attribute names made of 1-40 lowercase letters, digits or underscores.

    Attribute names become JSON keys, CSV content and page text, so they are restricted to a safe identifier form
    on the server; the browser editor's normalisation is only a convenience.
    """
    if not isinstance(value, list) or not value:
        raise ValidationError(
            "Enter a list of 1 to %(max)s attribute names.", code="invalid_list", params={"max": MAX_ATTRIBUTES}
        )
    if len(value) > MAX_ATTRIBUTES:
        raise ValidationError("Use at most %(max)s attributes.", code="too_many", params={"max": MAX_ATTRIBUTES})
    seen = set()
    for item in value:
        if not isinstance(item, str) or not ATTRIBUTE_NAME_PATTERN.fullmatch(item):
            raise ValidationError(
                "%(item)s is not a valid attribute name: use 1 to 40 lowercase letters, digits or underscores.",
                code="invalid_name",
                params={"item": repr(item)[:60]},
            )
        if item in seen:
            raise ValidationError("%(item)s is listed twice.", code="duplicate", params={"item": repr(item)})
        seen.add(item)
