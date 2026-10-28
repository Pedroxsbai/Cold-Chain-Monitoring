"""
Django settings for the Cold Chain Monitoring backend.

All environment-specific values are read from environment variables
(loaded from backend/.env in development). See .env.example.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    # Local apps
    "accounts",
    "monitoring",
    "incidents",
    "audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves the admin static files and the React build (single web app in production).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", BASE_DIR / "db.sqlite3"),
        # The web server and the alert engine write concurrently: wait for locks.
        "OPTIONS": {"timeout": 20},
    }
}


# Authentication

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization

LANGUAGE_CODE = "fr-fr"

TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Africa/Casablanca")

USE_I18N = True

USE_TZ = True


# Static files

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# React build (`npm run build` in frontend/). When present, Django serves it: its files
# from the site root (WhiteNoise), and index.html for every client-side route.
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))
if FRONTEND_DIST.is_dir():
    WHITENOISE_ROOT = FRONTEND_DIST

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Django REST Framework

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "DEFAULT_THROTTLE_RATES": {
        # Login and password reset, per client IP.
        "auth": os.environ.get("AUTH_THROTTLE_RATE", "10/min"),
        # Public acknowledgement links.
        "ack": os.environ.get("ACK_THROTTLE_RATE", "30/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "1"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}


# CORS (React dev server)

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")


# E-mail

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "coldchain@localhost")


# Cold chain monitoring
# Durations in minutes accept decimals, so a demo can run with e.g. NOTIFY_EVERY_MINUTES=0.5.

COLDCHAIN = {
    # Expected interval between two measurements from a node (firmware side).
    "MEASUREMENT_INTERVAL_MINUTES": float(os.environ.get("MEASUREMENT_INTERVAL_MINUTES", "20")),
    # A node is considered offline after this delay without measurement (2 cycles + margin).
    "OFFLINE_AFTER_MINUTES": float(os.environ.get("OFFLINE_AFTER_MINUTES", "45")),
    # Consecutive out-of-range measurements required to open an incident.
    "CONSECUTIVE_OUT_OF_RANGE": int(os.environ.get("CONSECUTIVE_OUT_OF_RANGE", "2")),
    # Delay between two notification rounds of the same open incident.
    "NOTIFY_EVERY_MINUTES": float(os.environ.get("NOTIFY_EVERY_MINUTES", "20")),
    # N2 joins after this many rounds, N3 after that many (N1 stays notified until the end).
    "ESCALATE_N2_AFTER_ROUNDS": int(os.environ.get("ESCALATE_N2_AFTER_ROUNDS", "4")),
    "ESCALATE_N3_AFTER_ROUNDS": int(os.environ.get("ESCALATE_N3_AFTER_ROUNDS", "8")),
    # Excursion durations triggering an immediate alert to all levels.
    "SEVERITY_HOURS": [float(h) for h in env_list("SEVERITY_HOURS", "5,8")],
    # Escalation resumes if the incident is still unfinished this long after acknowledgement.
    "RESUME_AFTER_ACK_MINUTES": float(os.environ.get("RESUME_AFTER_ACK_MINUTES", "120")),
    # Period of the alert engine (run_alert_engine).
    "TICK_SECONDS": int(os.environ.get("TICK_SECONDS", "30")),
    # Enabled channels, in sending order.
    "NOTIFY_CHANNELS": env_list("NOTIFY_CHANNELS", "ntfy,email"),
    "NTFY_SERVER": os.environ.get("NTFY_SERVER", "https://ntfy.sh"),
    "NTFY_TOKEN": os.environ.get("NTFY_TOKEN", ""),
    # Acknowledgement links sent in notifications.
    "ACK_LINK_MAX_AGE_HOURS": float(os.environ.get("ACK_LINK_MAX_AGE_HOURS", "24")),
    # Frontend URL (pages opened by users) and API URL (ntfy action buttons).
    "PUBLIC_BASE_URL": os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173"),
    "API_BASE_URL": os.environ.get("API_BASE_URL", "http://localhost:8000"),
    # Secret for POST /api/engine/tick/, called every minute by an external cron service
    # on hosts without a permanent process (PythonAnywhere). Empty: endpoint disabled.
    "ENGINE_TICK_TOKEN": os.environ.get("ENGINE_TICK_TOKEN", ""),
    # Daily SQLite backups (manage.py backup_db) and how many to keep.
    "BACKUP_DIR": os.environ.get("BACKUP_DIR", str(BASE_DIR / "backups")),
    "BACKUP_KEEP": int(os.environ.get("BACKUP_KEEP", "14")),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "loggers": {
        "incidents": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
    },
}


# Production hardening (active when DEBUG is off)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
