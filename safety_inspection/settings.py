"""
Django settings for safety_inspection project.
Reads all secrets from environment variables.
Copy .env.example → .env and fill in your values.
"""

from pathlib import Path
import os
import dj_database_url
from django.contrib.messages import constants as messages

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
# SECRET_KEY = os.environ.get(
#     "SECRET_KEY",
#     "django-insecure-change-me-before-production-do-not-use-this-key",
# )
SECRET_KEY = 'django-insecure-6cu)q-5rpqrf6*q(!uu%rwc(ip!p60003#km7whdf*usf*8p0f'

DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost 127.0.0.1").split()

# ---------------------------------------------------------------------------
# Installed apps
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "crispy_forms",
    "crispy_bootstrap5",
    "anymail",
    # Local apps
    "users.apps.UsersConfig",
    "observations.apps.ObservationsConfig",
    "core.apps.CoreConfig",
    "permits.apps.PermitsConfig",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",       # serve static in production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.OrganizationMiddleware",
    "core.middleware.SubscriptionMiddleware",
    "core.middleware.ContractorAccessMiddleware",      # restrict contractors to permits only
]

ROOT_URLCONF = "safety_inspection.urls"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.organization_context",
                "core.context_processors.trial_status",
            ],
        },
    },
]

WSGI_APPLICATION = "safety_inspection.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "users.CustomUser"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL          = "/users/accounts/login/"
LOGIN_REDIRECT_URL = "/"  # Home page with quick-launch dashboard
LOGOUT_REDIRECT_URL = "home"

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE     = "Asia/Kolkata"
USE_I18N      = True
USE_TZ        = True

# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Crispy Forms
# ---------------------------------------------------------------------------
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK          = "bootstrap5"

# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
MESSAGE_TAGS = {
    messages.DEBUG:   "secondary",
    messages.INFO:    "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR:   "danger",
}

# ---------------------------------------------------------------------------
# Default primary key
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Email — Brevo (Sendinblue)
# ---------------------------------------------------------------------------
BREVO_API_KEY     = os.environ.get("BREVO_API_KEY", "")
# DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "SafetySuite <noreply@yourdomain.com>")
DEFAULT_FROM_EMAIL = "Safety app <alset010@gmail.com>"


# ---------------------------------------------------------------------------
# Site URL — used in email links (no trailing slash)
# ---------------------------------------------------------------------------
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000")
# ---------------------------------------------------------------------------
# Razorpay
# ---------------------------------------------------------------------------
RAZORPAY_KEY_ID         = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET     = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")

# ---------------------------------------------------------------------------
# Security headers (only active when DEBUG=False)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_HSTS_SECONDS            = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_SSL_REDIRECT            = True
    SESSION_COOKIE_SECURE          = True
    CSRF_COOKIE_SECURE             = True
    SECURE_BROWSER_XSS_FILTER      = True
    SECURE_CONTENT_TYPE_NOSNIFF    = True
    X_FRAME_OPTIONS                = "DENY"
