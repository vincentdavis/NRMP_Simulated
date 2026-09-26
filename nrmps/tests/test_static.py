"""Vendored browser libraries survive collectstatic (plan step 5.1)."""

import re
from pathlib import Path

from django.conf import settings

VENDOR = Path(settings.BASE_DIR, "static", "vendor")


def test_every_source_map_a_vendored_file_points_to_is_vendored_too():
    """The manifest storage resolves `sourceMappingURL` references when it hashes files, so a missing map fails
    collectstatic and with it the Docker build (graphology's did)."""
    missing = []
    for path in VENDOR.rglob("*.js"):
        reference = re.search(r"//# sourceMappingURL=(\S+)\s*$", path.read_text(encoding="utf-8", errors="replace"))
        if reference and not (path.parent / reference.group(1)).is_file():
            missing.append(f"{path.relative_to(VENDOR)} -> {reference.group(1)}")
    assert missing == []


def test_every_vendored_library_has_its_licence():
    for folder in (version for library in VENDOR.iterdir() if library.is_dir() for version in library.iterdir()):
        licences = [name for name in ("LICENSE", "LICENSE.md", "LICENSE.txt") if (folder / name).is_file()]
        assert licences or folder.parent.name == "alpinejs", folder  # Alpine's npm package ships no licence file
