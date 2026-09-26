"""Settings for the test suite.

Tests run the production configuration (DEBUG off, production apps and middleware) with test-only secrets and an
isolated database. The database is SQLite in memory unless NRMP_TEST_DATABASE_URL points elsewhere (for example a
local PostgreSQL); DATABASE_URL is deliberately ignored so tests can never touch a real database.
"""

import os

os.environ["DEBUG"] = "False"
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz")
os.environ["DATABASE_URL"] = os.environ.get("NRMP_TEST_DATABASE_URL") or "sqlite:///:memory:"
os.environ["LOGFIRE_SEND_TO_LOGFIRE"] = "false"

from .settings import *  # noqa: F403

# The test client speaks plain HTTP.
SECURE_SSL_REDIRECT = False

# Tests do not run collectstatic, so use plain static storage instead of the production manifest storage.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Fast password hashing for tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
