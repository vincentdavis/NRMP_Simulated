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
from django.utils.csp import CSP

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
    "django_tasks_db",
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
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
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
                "django.template.context_processors.csp",
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
# SQLite: the web server and the worker (TASK_BACKEND=database) can share the file. Transactions start IMMEDIATE,
# taking the write lock at BEGIN and waiting up to `timeout` seconds for it. The default, DEFERRED, reads first and
# then fails at once with "database is locked" when it needs to write while the other process is writing.
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {}).update({"transaction_mode": "IMMEDIATE", "timeout": 20})


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

# Background runs (plan step 2.5, decision D5): django.tasks. With TASK_BACKEND=immediate (the default) a run executes
# inside the web request that starts it; with TASK_BACKEND=database runs are queued in the database and a worker
# service executes them (`manage.py nrmp_worker`).
TASK_BACKEND = os.environ.get("TASK_BACKEND", "immediate").strip().lower()
if TASK_BACKEND == "database":
    TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend", "QUEUES": ["default"]}}
elif TASK_BACKEND == "immediate":
    TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}
else:
    raise ImproperlyConfigured("TASK_BACKEND must be 'immediate' or 'database'.")

# Largest applicants x programs product of one run (decision D4): NRMP_MAX_PAIRS when runs execute in the request,
# NRMP_MAX_PAIRS_WORKER when a worker executes them. The engine takes about 0.35 s per million pairs.
NRMP_MAX_PAIRS = int(os.environ.get("NRMP_MAX_PAIRS", "1000000"))
NRMP_MAX_PAIRS_WORKER = int(os.environ.get("NRMP_MAX_PAIRS_WORKER", "10000000"))
# Pairs the engine computes at a time: its memory use is about 100 bytes per block pair (docs/model_spec.md §12.7).
# Results do not depend on it.
NRMP_BLOCK_PAIRS = int(os.environ.get("NRMP_BLOCK_PAIRS", "250000"))
# Largest market for which the detail pages compute the other side's ranks and the pairs CSV is offered: both need
# every pair of the market to be recomputed during the request.
NRMP_DRILLDOWN_MAX_PAIRS = int(os.environ.get("NRMP_DRILLDOWN_MAX_PAIRS", "2000000"))

# Quotas per account (staff are exempt). With NRMP_REQUIRE_VERIFIED_EMAIL, accounts must confirm their email address
# before they can run simulations; turn it on once outgoing email works.
NRMP_REQUIRE_VERIFIED_EMAIL = env_bool("NRMP_REQUIRE_VERIFIED_EMAIL", default=False)
NRMP_MAX_SIMULATIONS = int(os.environ.get("NRMP_MAX_SIMULATIONS", "50"))
NRMP_MAX_PRESETS = int(os.environ.get("NRMP_MAX_PRESETS", "50"))
NRMP_RUNS_PER_DAY = int(os.environ.get("NRMP_RUNS_PER_DAY", "200"))
NRMP_PAIRS_PER_DAY = int(os.environ.get("NRMP_PAIRS_PER_DAY", "200000000"))
# Rate limits ("count/period" with period s, m, h or d), counted in the database: sign-ups per client address, and
# runs and uploads per account.
NRMP_RATE_LIMITS = {
    "signup": os.environ.get("NRMP_RATE_SIGNUP", "10/h"),
    "run": os.environ.get("NRMP_RATE_RUN", "60/h"),
    "upload": os.environ.get("NRMP_RATE_UPLOAD", "60/h"),
}
# Housekeeping (`manage.py nrmp_cleanup`): runs kept per simulation, and how long a run may stay queued or running
# before it counts as interrupted.
NRMP_RUNS_KEPT = int(os.environ.get("NRMP_RUNS_KEPT", "50"))
NRMP_STALE_RUN_MINUTES = int(os.environ.get("NRMP_STALE_RUN_MINUTES", "60"))
# A run's page warns when it has been queued for longer than this (runs normally start within seconds).
NRMP_QUEUE_WARNING_SECONDS = int(os.environ.get("NRMP_QUEUE_WARNING_SECONDS", "60"))

# Email (Django 6.1 MAILERS): SMTP when EMAIL_HOST is set (any provider: Postmark, SendGrid, Mailgun, SES ...);
# otherwise messages are written to the log, which is enough for development.
_smtp_host = os.environ.get("EMAIL_HOST", "").strip()
if _smtp_host:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": _smtp_host,
                "port": int(os.environ.get("EMAIL_PORT", "587")),
                "username": os.environ.get("EMAIL_HOST_USER", ""),
                "password": os.environ.get("EMAIL_HOST_PASSWORD", ""),
                "use_tls": env_bool("EMAIL_USE_TLS", default=True),
                "timeout": 10,
            },
        }
    }
else:
    MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "NRMP Simulations <noreply@nrmp-simulated.heteroskedastic.org>"
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Email verification and password reset links stay valid for three days.
PASSWORD_RESET_TIMEOUT = 3 * 24 * 60 * 60

# Public contact details shown on the contact, privacy and terms pages. Without CONTACT_EMAIL only the issue tracker
# is offered.
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "").strip()
PROJECT_URL = "https://github.com/vincentdavis/NRMP_Simulated"
# Absolute address of the site, for links in emails sent outside a request (for example "run finished").
SITE_URL = os.environ.get("SITE_URL", "").strip().rstrip("/") or (
    f"https://{railway_domain}" if railway_domain else "https://nrmp-simulated.heteroskedastic.org"
)

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


# Content Security Policy (plan step 5.1, ENG-22), report-only for now: browsers report what the policy would block to
# /csp-report/ (logged by nrmps.views.csp_report) and block nothing. Step 5.5 enforces it (SECURE_CSP) once the list
# editors use Alpine's CSP build, which lets 'unsafe-eval' go. Every script is a static file; the one inline script
# (the theme, in theme/templates/base.html) carries the request's nonce. Style attributes stay allowed (the help
# popovers' anchor positioning, bar widths). Libraries are vendored, never loaded from a CDN.
SECURE_CSP_REPORT_ONLY = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE, CSP.UNSAFE_EVAL, CSP.REPORT_SAMPLE],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "report-uri": ["/csp-report/"],
}


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

    # An explicit argument would override LOGFIRE_SEND_TO_LOGFIRE, so honour "false" here (tests and CI set it).
    _send_to_logfire = os.environ.get("LOGFIRE_SEND_TO_LOGFIRE", "").strip().lower() not in {"false", "0", "no", "off"}
    logfire.configure(
        send_to_logfire="if-token-present" if _send_to_logfire else False,
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
