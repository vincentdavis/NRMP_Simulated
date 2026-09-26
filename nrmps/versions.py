"""Version stamps stored with every run and export (docs/model_spec.md §12.11)."""

import os
import platform
import tomllib
from functools import cache
from pathlib import Path

import numpy as np

from .engine import ENGINE_VERSION, MODEL_VERSION
from .params import SCHEMA_VERSION

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


@cache
def app_version() -> str:
    """Return the project version from pyproject.toml ("unknown" if it cannot be read)."""
    try:
        with PYPROJECT.open("rb") as file:
            return str(tomllib.load(file)["project"]["version"])
    except OSError, KeyError, tomllib.TOMLDecodeError:
        return "unknown"


def git_sha() -> str:
    """Return the deployed commit: GIT_SHA (set when the image is built) or Railway's RAILWAY_GIT_COMMIT_SHA."""
    return os.environ.get("GIT_SHA") or os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")


def stamps() -> dict[str, str | int]:
    """Return every version stamp of the running code."""
    return {
        "model_version": MODEL_VERSION,
        "engine_version": ENGINE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "app_version": app_version(),
        "git_sha": git_sha(),
        "numpy_version": np.__version__,
        "python_version": platform.python_version(),
    }
