"""Every CSS class used in templates and form widgets exists in the built stylesheet (plan step 1.4, UX-8).

daisyUI 5 renamed or dropped many daisyUI 4 classes (form-control, label-text, *-bordered, card-header ...), and
Tailwind only emits the classes it finds, so a class missing from the built CSS is either a typo or dead markup.
This test needs the built CSS (`npm run build` in theme/static_src). It is skipped when the file is absent, unless
NRMP_REQUIRE_BUILT_CSS is set (CI).
"""

import os
import re
from pathlib import Path

import pytest
from django.conf import settings

CSS_FILE = Path(settings.BASE_DIR) / "theme" / "static" / "css" / "dist" / "styles.css"
TEMPLATE_DIRS = [Path(settings.BASE_DIR) / "templates", Path(settings.BASE_DIR) / "theme" / "templates"]
PYTHON_DIRS = [Path(settings.BASE_DIR) / "nrmps"]

# Classes that are hooks for scripts or styled by a library's own CSS rather than the built stylesheet.
UNSTYLED_HOOKS = {
    "htmx-indicator",  # htmx injects the rule that shows it while a request runs
}

CLASS_ATTRIBUTE = re.compile(r"""(?<![:\w-])class\s*=\s*(["'])(.*?)\1""", re.S)
PYTHON_CLASS = re.compile(r"""["']class["']\s*:\s*["']([^"']*)["']""")
TEMPLATE_TAG = re.compile(r"{%.*?%}|{{.*?}}", re.S)


def _css_escape(token: str) -> str:
    """Escape a class name the way it appears in a CSS selector."""
    return re.sub(r"([^a-zA-Z0-9_-])", r"\\\1", token)


def _used_classes() -> dict[str, set[str]]:
    """Map each class token to the files that use it."""
    used: dict[str, set[str]] = {}
    for root in TEMPLATE_DIRS:
        for path in root.rglob("*.html"):
            for _, value in CLASS_ATTRIBUTE.findall(path.read_text()):
                # Keep the literal text of {% if %} branches; drop the tags and {{ variables }}.
                for token in TEMPLATE_TAG.sub(" ", value).split():
                    used.setdefault(token, set()).add(path.name)
    for root in PYTHON_DIRS:
        for path in root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            for value in PYTHON_CLASS.findall(path.read_text()):
                for token in value.split():
                    used.setdefault(token, set()).add(path.name)
    return used


def test_every_used_class_exists_in_the_built_css():
    if not CSS_FILE.exists():
        if os.environ.get("NRMP_REQUIRE_BUILT_CSS"):
            pytest.fail(f"{CSS_FILE} not found; build it with `npm run build` in theme/static_src")
        pytest.skip("built CSS not found; run `npm run build` in theme/static_src")
    css = CSS_FILE.read_text()
    missing = {
        token: sorted(files)
        for token, files in sorted(_used_classes().items())
        if token not in UNSTYLED_HOOKS and not re.search(rf"\.{re.escape(_css_escape(token))}(?![\w-])", css)
    }
    assert missing == {}, "Classes with no CSS rule (daisyUI 4 leftovers or typos):\n" + "\n".join(
        f"  {token}: {', '.join(files)}" for token, files in missing.items()
    )
