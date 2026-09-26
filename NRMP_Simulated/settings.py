"""Django settings for NRMP_Simulated project.

Configuration comes from environment variables. For local development, put them in a `.env` file at the project
root (see `.env.example`); real environment variables take precedence over the file.

Production (DEBUG off) refuses to start without `SECRET_KEY` and `DATABASE_URL`.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.1/ref/settings/
"""

import os
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Load `KEY=VALUE` lines from a `.env` file without overriding variables that are already set."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable ("true", "1", "yes" and "on" count as true)."""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"true", "1", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable as a list of non-empty, stripped items."""
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# A local .env file is for development only; on Railway the platform's variables are the only source.
if not (os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("RAILWAY_ENVIRONMENT_ID")):
    _load_dotenv(BASE_DIR / ".env")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool("DEBUG", default=False)

# SECURITY WARNING: keep the secret key used in production secret!
# The development key is only used when DEBUG is on; production must set SECRET_KEY.
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "SECRET_KEY must be set when DEBUG is off. For local development set DEBUG=True (see .env.example)."
        )
    SECRET_KEY = "django-insecure-development-only-key-never-use-in-production"  # noqa: S105 (DEBUG only)

# Hosts: ALLOWED_HOSTS from the environment, plus Railway's public domain when present.
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,nrmp-simulated.heteroskedastic.org")
railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
if railway_domain:
    ALLOWED_HOSTS.insert(0, railway_domain)
if os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("RAILWAY_ENVIRONMENT_ID"):
    # Railway's deploy health check (GET /healthz) arrives with this host name.
    ALLOWED_HOSTS.append("healthcheck.railway.app")

# CSRF trusted origins. With SECURE_PROXY_SSL_HEADER (below), same-origin HTTPS posts pass the origin check without
# being listed here; list extra origins in CSRF_TRUSTED_ORIGINS if needed.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if railway_domain:
    CSRF_TRUSTED_ORIGINS.append(f"https://{railway_domain}")

AUTH_USER_MODEL = "nrmps.User"

INTERNAL_IPS = [
    "127.0.0.1",
]


# Application definition

TAILWIND_APP_NAME = "theme"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    #### Sub Apps
    "nrmps.apps.NrmpsConfig",
    #### Plugin and addons
    "tailwind",
    "theme",
    "django_htmx",
    "axes",
]

# Development-only apps (installed with the dev dependency group)
if DEBUG:
    INSTALLED_APPS += [
        "debug_toolbar",
        "reset_migrations",
        "django_browser_reload",
    ]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Static files for production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Every page needs a signed-in user unless its view is marked @login_not_required.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ### Add-ons
    "django_htmx.middleware.HtmxMiddleware",
    # Last, as django-axes requires.
    "axes.middleware.AxesMiddleware",
]

# Development-only middleware
if DEBUG:
    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        "django_browser_reload.middleware.BrowserReloadMiddleware",
    ]

ROOT_URLCONF = "NRMP_Simulated.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "theme" / "templates", BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "nrmps.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "NRMP_Simulated.wsgi.application"


# Database
# PostgreSQL in production (Railway) via DATABASE_URL. Without DATABASE_URL, development (DEBUG on) falls back to a
# local SQLite file; production refuses to start rather than silently writing to the container's ephemeral disk.
# An explicit sqlite:///... URL is allowed everywhere (the image build and CI use one).

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    import dj_database_url

    # Reuse connections across requests; check them before reuse so a restarted database is not an error.
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, conn_health_checks=True)}
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    }
else:
    raise ImproperlyConfigured(
        "DATABASE_URL must be set when DEBUG is off (use sqlite:///path/to/file.sqlite3 for a local SQLite database)."
    )


# Authentication. django-axes comes first so it can refuse sign-ins from a locked-out client.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Login throttling (django-axes): after 5 failed sign-ins for the same username from the same client, that pair is
# locked out for 15 minutes. Successful sign-ins are not logged.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_DISABLE_ACCESS_LOG = True
AXES_LOCKOUT_TEMPLATE = "registration/lockout.html"
AXES_CLIENT_IP_CALLABLE = "nrmps.security.client_ip"
# Reverse proxies in front of the app that append to X-Forwarded-For: Railway's edge in production, none locally.
TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0" if DEBUG else "1"))

# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = "static/"
# Project-level static directory for development assets (images, JS, CSS)
STATICFILES_DIRS = [BASE_DIR / "static"]

# Directory where collectstatic will gather files for production
STATIC_ROOT = BASE_DIR / "staticfiles"

# In production WhiteNoise serves compressed files with content-hashed names and long cache lifetimes; that needs the
# manifest `collectstatic` writes (the image build runs it).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/6.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Largest applicants x programs product a single simulation step may process (decision D4). Steps run inside the web
# request until background jobs exist, so this keeps every step well within the gunicorn timeout.
NRMP_MAX_PAIRS = int(os.environ.get("NRMP_MAX_PAIRS", "250000"))

# Public contact details shown on the contact, privacy and terms pages. Without CONTACT_EMAIL only the issue tracker
# is offered.
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "").strip()
PROJECT_URL = "https://github.com/vincentdavis/NRMP_Simulated"

# Authentication redirects
LOGIN_REDIRECT_URL = "nrmps:index"
LOGOUT_REDIRECT_URL = "nrmps:index"
LOGIN_URL = "nrmps:login"


# HTTPS behind Railway's TLS-terminating proxy (production only).
if not DEBUG:
    # Railway terminates TLS and forwards the original scheme; trust it so request.is_secure() and the CSRF origin
    # check see https.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_REDIRECT_EXEMPT = [r"^healthz/?$"]
    # Cookies only over HTTPS. SECURE_COOKIES=False is for running the production image over plain http://localhost.
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", default=True)
    # Start low and raise to 31536000 once HTTPS is confirmed everywhere. Subdomains and preload stay off on
    # purpose (other services may share the parent domain), so their deploy-check warnings are silenced; any other
    # `check --deploy` warning fails CI.
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
    SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]


# Logging. Logfire is used in production only, and only sends data when a token is configured.
LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        # Ensure our app logs show up in development
        "nrmps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

if not DEBUG:
    import logfire

    logfire.configure(
        send_to_logfire="if-token-present",
        console=False,
        service_name="nrmp-simulated",
        environment=os.environ.get("RAILWAY_ENVIRONMENT_NAME", "local"),
        # Besides Logfire's default patterns (password, token, secret, ...), redact account details.
        scrubbing=logfire.ScrubbingOptions(extra_patterns=["email", "full_name", "username"]),
    )
    # Static files and the health check are not worth a trace each.
    logfire.instrument_django(excluded_urls="/static/.*,/healthz")

    LOGGING["handlers"]["logfire"] = {
        "class": "logfire.LogfireLoggingHandler",
        "level": "INFO",
    }
    LOGGING["root"]["handlers"] = ["logfire", "console"]
    LOGGING["loggers"]["nrmps"]["handlers"] = ["logfire", "console"]
