import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ[key] = value


load_env_file(BASE_DIR / ".env")


def get_env(name: str, default: str) -> str:
    return os.getenv(name, default)


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def get_list_env(name: str, default: list[str] | tuple[str, ...] | None = None) -> list[str]:
    value = os.getenv(name)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = get_env("DJANGO_SECRET_KEY", "django-insecure-change-me")
DEBUG = get_bool_env("DJANGO_DEBUG", False)
ALLOWED_HOSTS = get_list_env("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = get_list_env("DJANGO_CSRF_TRUSTED_ORIGINS", [])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core.apps.CoreConfig",
    "apps.people.apps.PeopleConfig",
    "apps.wristbands.apps.WristbandsConfig",
    "apps.access.apps.AccessConfig",
    "apps.controllers.apps.ControllersConfig",
    "apps.events.apps.EventsConfig",
    "apps.fondvision_integration.apps.FondvisionIntegrationConfig",
    "apps.ironlogic_integration.apps.IronlogicIntegrationConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "skud_local.urls"

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

WSGI_APPLICATION = "skud_local.wsgi.application"
ASGI_APPLICATION = "skud_local.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": get_env("POSTGRES_DB", "skud_local"),
        "USER": get_env("POSTGRES_USER", "skud"),
        "PASSWORD": get_env("POSTGRES_PASSWORD", "skud_local_password"),
        "HOST": get_env("POSTGRES_HOST", "db"),
        "PORT": get_env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": get_int_env("DATABASE_CONN_MAX_AGE", 60),
        "OPTIONS": {
            "connect_timeout": get_int_env("DATABASE_CONNECT_TIMEOUT", 5),
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = get_env("DJANGO_LANGUAGE_CODE", "ru-ru")
TIME_ZONE = get_env("DJANGO_TIME_ZONE", "Asia/Almaty")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = get_bool_env("DJANGO_USE_X_FORWARDED_HOST", False)
SECURE_SSL_REDIRECT = get_bool_env("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = get_bool_env("DJANGO_SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = get_bool_env("DJANGO_CSRF_COOKIE_SECURE", False)
SECURE_HSTS_SECONDS = get_int_env("DJANGO_SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_bool_env("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = get_bool_env("DJANGO_SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"

rest_renderer_classes = ["rest_framework.renderers.JSONRenderer"]
if DEBUG:
    rest_renderer_classes.append("rest_framework.renderers.BrowsableAPIRenderer")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": rest_renderer_classes,
    "DEFAULT_PAGINATION_CLASS": "apps.core.api.pagination.DefaultPageNumberPagination",
    "PAGE_SIZE": 50,
}

IRONLOGIC_WEBJSON_SHARED_TOKEN = get_env("IRONLOGIC_WEBJSON_SHARED_TOKEN", "")
IRONLOGIC_ALLOWED_IPS = get_list_env("IRONLOGIC_ALLOWED_IPS", [])
IRONLOGIC_TRUST_X_FORWARDED_FOR = get_bool_env("IRONLOGIC_TRUST_X_FORWARDED_FOR", False)
IRONLOGIC_AUTO_ACTIVATE_ON_POWER_ON = get_bool_env("IRONLOGIC_AUTO_ACTIVATE_ON_POWER_ON", True)
IRONLOGIC_ONLINE_ACCESS_ENABLED = get_bool_env("IRONLOGIC_ONLINE_ACCESS_ENABLED", True)
IRONLOGIC_RESPONSE_INTERVAL_SECONDS = get_int_env("IRONLOGIC_RESPONSE_INTERVAL_SECONDS", 10)
IRONLOGIC_TASK_BATCH_SIZE = get_int_env("IRONLOGIC_TASK_BATCH_SIZE", 20)
IRONLOGIC_TASK_BATCH_MAX_BYTES = get_int_env("IRONLOGIC_TASK_BATCH_MAX_BYTES", 16384)
IRONLOGIC_TASK_SENT_RETRY_SECONDS = get_int_env("IRONLOGIC_TASK_SENT_RETRY_SECONDS", 120)
IRONLOGIC_SYNC_WRISTBAND_CHUNK_SIZE = get_int_env("IRONLOGIC_SYNC_WRISTBAND_CHUNK_SIZE", 200)
FONDVISION_CONTROLLER_USERNAME = get_env("FONDVISION_CONTROLLER_USERNAME", "z5rweb")
FONDVISION_CONTROLLER_PASSWORD = get_env("FONDVISION_CONTROLLER_PASSWORD", "DD4DF9F2")
FONDVISION_CONTROLLER_TIMEOUT_SECONDS = get_int_env("FONDVISION_CONTROLLER_TIMEOUT_SECONDS", 12)
FONDVISION_COMMAND_RELAY_URL = get_env("FONDVISION_COMMAND_RELAY_URL", "")
FONDVISION_COMMAND_RELAY_TOKEN = get_env("FONDVISION_COMMAND_RELAY_TOKEN", "")
FONDVISION_COMMAND_RELAY_TIMEOUT_SECONDS = get_int_env("FONDVISION_COMMAND_RELAY_TIMEOUT_SECONDS", 15)
FONDVISION_QR_PASSWORD = get_env(
    "FONDVISION_QR_PASSWORD",
    "om9HP1LSkx2BppF3vFz32nV2YI5D/B+moxFH/6/qer4=",
)
FONDVISION_QR_B_SUFFIX_REQUIRED_FROM = get_env("FONDVISION_QR_B_SUFFIX_REQUIRED_FROM", "2026-04-10")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": get_env("DJANGO_LOG_LEVEL", "INFO"),
    },
}
