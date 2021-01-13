"""
Django settings for ocw_studio.
"""
import logging
import os
import platform

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from main.envs import (
    get_any,
    get_bool,
    get_int,
    get_string,
)
from main.sentry import init_sentry

VERSION = "0.0.0"

SITE_ID = get_int("OCW_STUDIO_SITE_ID", 1)

# Sentry
ENVIRONMENT = get_string("OCW_STUDIO_ENVIRONMENT", "dev")
# this is only available to heroku review apps
HEROKU_APP_NAME = get_string(
    "HEROKU_APP_NAME", None, description="The name of the review app"
)

# initialize Sentry before doing anything else so we capture any config errors
SENTRY_DSN = get_string(
    "SENTRY_DSN", "", description="The connection settings for Sentry"
)
SENTRY_LOG_LEVEL = get_string(
    "SENTRY_LOG_LEVEL", "ERROR", description="The log level for Sentry"
)
init_sentry(
    dsn=SENTRY_DSN,
    environment=ENVIRONMENT,
    version=VERSION,
    log_level=SENTRY_LOG_LEVEL,
    heroku_app_name=HEROKU_APP_NAME,
)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_string("SECRET_KEY", None)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = get_bool("DEBUG", False)

ALLOWED_HOSTS = ["*"]

SECURE_SSL_REDIRECT = get_bool("OCW_STUDIO_SECURE_SSL_REDIRECT", True)


WEBPACK_LOADER = {
    "DEFAULT": {
        "CACHE": not DEBUG,
        "BUNDLE_DIR_NAME": "bundles/",
        "STATS_FILE": os.path.join(BASE_DIR, "webpack-stats.json"),
        "POLL_INTERVAL": 0.1,
        "TIMEOUT": None,
        "IGNORE": [r".+\.hot-update\.+", r".+\.js\.map"],
    }
}


# configure a custom user model
AUTH_USER_MODEL = "users.User"

# Application definition
INSTALLED_APPS = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "server_status",
    # django-robots
    "robots",
    # Put our apps after this point
    "main",
    "users",
    "websites",
)

DISABLE_WEBPACK_LOADER_STATS = get_bool("DISABLE_WEBPACK_LOADER_STATS", False)
if not DISABLE_WEBPACK_LOADER_STATS:
    INSTALLED_APPS += ("webpack_loader",)

MIDDLEWARE = (
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.sites.middleware.CurrentSiteMiddleware",
    "main.middleware.CachelessAPIMiddleware",
)

# enable the nplusone profiler only in debug mode
if DEBUG:
    INSTALLED_APPS += ("nplusone.ext.django",)
    MIDDLEWARE += ("nplusone.ext.django.NPlusOneMiddleware",)

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/"
LOGIN_ERROR_URL = "/"

ROOT_URLCONF = "main.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "main.wsgi.application"


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases
DEFAULT_DATABASE_CONFIG = dj_database_url.parse(
    get_string(
        "DATABASE_URL",
        "sqlite:///{0}".format(os.path.join(BASE_DIR, "db.sqlite3")),
        description="The connection url to the Postgres database",
        required=True,
        write_app_json=False,
    )
)
DEFAULT_DATABASE_CONFIG["CONN_MAX_AGE"] = get_int(
    "OCW_STUDIO_DB_CONN_MAX_AGE",
    0,
    description="Maximum age of connection to Postgres in seconds",
)
# If True, disables server-side database cursors to prevent invalid cursor errors when using pgbouncer
DEFAULT_DATABASE_CONFIG["DISABLE_SERVER_SIDE_CURSORS"] = get_bool(
    "OCW_STUDIO_DB_DISABLE_SS_CURSORS", True
)

if get_bool("OCW_STUDIO_DB_DISABLE_SSL", False):
    DEFAULT_DATABASE_CONFIG["OPTIONS"] = {}
else:
    DEFAULT_DATABASE_CONFIG["OPTIONS"] = {"sslmode": "require"}

DATABASES = {"default": DEFAULT_DATABASE_CONFIG}

# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

# django-robots
ROBOTS_USE_HOST = False
ROBOTS_CACHE_TIMEOUT = get_int("ROBOTS_CACHE_TIMEOUT", 60 * 60 * 24)

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

# Serve static files with dj-static
STATIC_URL = "/static/"
STATIC_ROOT = "staticfiles"
STATICFILES_DIRS = (os.path.join(BASE_DIR, "static"),)

# Request files from the webpack dev server
USE_WEBPACK_DEV_SERVER = get_bool("OCW_STUDIO_USE_WEBPACK_DEV_SERVER", False)
WEBPACK_DEV_SERVER_HOST = get_string("WEBPACK_DEV_SERVER_HOST", "")
WEBPACK_DEV_SERVER_PORT = get_int("WEBPACK_DEV_SERVER_PORT", 8042)

# Important to define this so DEBUG works properly
INTERNAL_IPS = (get_string("HOST_IP", "127.0.0.1"),)

# Configure e-mail settings
EMAIL_BACKEND = get_string(
    "OCW_STUDIO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = get_string("OCW_STUDIO_EMAIL_HOST", "localhost")
EMAIL_PORT = get_int("OCW_STUDIO_EMAIL_PORT", 25)
EMAIL_HOST_USER = get_string("OCW_STUDIO_EMAIL_USER", "")
EMAIL_HOST_PASSWORD = get_string("OCW_STUDIO_EMAIL_PASSWORD", "")
EMAIL_USE_TLS = get_bool("OCW_STUDIO_EMAIL_TLS", False)
EMAIL_SUPPORT = get_string("OCW_STUDIO_SUPPORT_EMAIL", "support@example.com")
DEFAULT_FROM_EMAIL = get_string("OCW_STUDIO_FROM_EMAIL", "webmaster@localhost")

MAILGUN_URL = get_string("MAILGUN_URL", None)
MAILGUN_KEY = get_string("MAILGUN_KEY", None)
MAILGUN_BATCH_CHUNK_SIZE = get_int("MAILGUN_BATCH_CHUNK_SIZE", 1000)
MAILGUN_RECIPIENT_OVERRIDE = get_string("MAILGUN_RECIPIENT_OVERRIDE", None)
MAILGUN_FROM_EMAIL = get_string("MAILGUN_FROM_EMAIL", "no-reply@example.com")


# e-mail configurable admins
ADMIN_EMAIL = get_string("OCW_STUDIO_ADMIN_EMAIL", "")
if ADMIN_EMAIL != "":
    ADMINS = (("Admins", ADMIN_EMAIL),)
else:
    ADMINS = ()

# Logging configuration
LOG_LEVEL = get_string("OCW_STUDIO_LOG_LEVEL", "INFO")
DJANGO_LOG_LEVEL = get_string("DJANGO_LOG_LEVEL", "INFO")

# For logging to a remote syslog host
LOG_HOST = get_string("OCW_STUDIO_LOG_HOST", "localhost")
LOG_HOST_PORT = get_int("OCW_STUDIO_LOG_HOST_PORT", 514)

HOSTNAME = platform.node().split(".")[0]

# nplusone profiler logger configuration
NPLUSONE_LOGGER = logging.getLogger("nplusone")
NPLUSONE_LOG_LEVEL = logging.ERROR

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        }
    },
    "formatters": {
        "verbose": {
            "format": (
                "[%(asctime)s] %(levelname)s %(process)d [%(name)s] "
                "%(filename)s:%(lineno)d - "
                "[{hostname}] - %(message)s"
            ).format(hostname=HOSTNAME),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "syslog": {
            "level": LOG_LEVEL,
            "class": "logging.handlers.SysLogHandler",
            "facility": "local7",
            "formatter": "verbose",
            "address": (LOG_HOST, LOG_HOST_PORT),
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        "django": {
            "propagate": True,
            "level": DJANGO_LOG_LEVEL,
            "handlers": ["console", "syslog"],
        },
        "django.request": {
            "handlers": ["mail_admins"],
            "level": DJANGO_LOG_LEVEL,
            "propagate": True,
        },
        "nplusone": {
            "handlers": ["console"],
            "level": "ERROR",
        },
    },
    "root": {
        "handlers": ["console", "syslog"],
        "level": LOG_LEVEL,
    },
}

# server-status
STATUS_TOKEN = get_string("STATUS_TOKEN", "")
HEALTH_CHECK = ["CELERY", "REDIS", "POSTGRES"]

GA_TRACKING_ID = get_string("GA_TRACKING_ID", "")
REACT_GA_DEBUG = get_bool("REACT_GA_DEBUG", False)

MEDIA_ROOT = get_string("MEDIA_ROOT", "/var/media/")
MEDIA_URL = "/media/"
OCW_STUDIO_USE_S3 = get_bool("OCW_STUDIO_USE_S3", False)
MAX_S3_GET_ITERATIONS = get_int(
    "MAX_S3_GET_ITERATIONS", 3, description="Max retry attempts to get an S3 object"
)
AWS_ACCESS_KEY_ID = get_string("AWS_ACCESS_KEY_ID", False)
AWS_SECRET_ACCESS_KEY = get_string("AWS_SECRET_ACCESS_KEY", False)
AWS_STORAGE_BUCKET_NAME = get_string("AWS_STORAGE_BUCKET_NAME", False)
AWS_QUERYSTRING_AUTH = get_string("AWS_QUERYSTRING_AUTH", False)
# Provide nice validation of the configuration
if OCW_STUDIO_USE_S3 and (
    not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY or not AWS_STORAGE_BUCKET_NAME
):
    raise ImproperlyConfigured(
        "You have enabled S3 support, but are missing one of "
        "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or "
        "AWS_STORAGE_BUCKET_NAME"
    )
if OCW_STUDIO_USE_S3:
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

# Celery
REDISCLOUD_URL = get_string(
    "REDISCLOUD_URL", None, description="RedisCloud connection url"
)
if REDISCLOUD_URL is not None:
    _redis_url = REDISCLOUD_URL
else:
    _redis_url = get_string(
        "REDIS_URL", None, description="Redis URL for non-production use"
    )

CELERY_BROKER_URL = get_string(
    "CELERY_BROKER_URL",
    _redis_url,
    description="Where celery should get tasks, default is Redis URL",
)
CELERY_RESULT_BACKEND = get_string(
    "CELERY_RESULT_BACKEND",
    _redis_url,
    description="Where celery should put task results, default is Redis URL",
)
CELERY_TASK_ALWAYS_EAGER = get_bool("CELERY_TASK_ALWAYS_EAGER", False, dev_only=True)
CELERY_TASK_EAGER_PROPAGATES = get_bool("CELERY_TASK_EAGER_PROPAGATES", True)

CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"


# django cache back-ends
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "local-in-memory-cache",
    },
    "redis": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": CELERY_BROKER_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    },
}


# features flags
def get_all_config_keys():
    """Returns all the configuration keys from both environment and configuration files"""
    return list(os.environ.keys())


OCW_STUDIO_FEATURES_PREFIX = get_string("OCW_STUDIO_FEATURES_PREFIX", "FEATURE_")
FEATURES = {
    key[len(OCW_STUDIO_FEATURES_PREFIX) :]: get_any(key, None)
    for key in get_all_config_keys()
    if key.startswith(OCW_STUDIO_FEATURES_PREFIX)
}

MIDDLEWARE_FEATURE_FLAG_QS_PREFIX = get_string(
    "MIDDLEWARE_FEATURE_FLAG_QS_PREFIX", None
)
MIDDLEWARE_FEATURE_FLAG_COOKIE_NAME = get_string(
    "MIDDLEWARE_FEATURE_FLAG_COOKIE_NAME",
    "OCW_STUDIO_FEATURE_FLAGS",
)
MIDDLEWARE_FEATURE_FLAG_COOKIE_MAX_AGE_SECONDS = get_int(
    "MIDDLEWARE_FEATURE_FLAG_COOKIE_MAX_AGE_SECONDS", 60 * 60
)

if MIDDLEWARE_FEATURE_FLAG_QS_PREFIX:
    MIDDLEWARE = MIDDLEWARE + (
        "main.middleware.QueryStringFeatureFlagMiddleware",
        "main.middleware.CookieFeatureFlagMiddleware",
    )


# django debug toolbar only in debug mode
if DEBUG:
    INSTALLED_APPS += ("debug_toolbar",)
    # it needs to be enabled before other middlewares
    MIDDLEWARE = ("debug_toolbar.middleware.DebugToolbarMiddleware",) + MIDDLEWARE

# List of mandatory settings. If any of these is not set, the app will not start
# and will raise an ImproperlyConfigured exception
MANDATORY_SETTINGS = [
    "MAILGUN_URL",
    "MAILGUN_KEY",
    "SECRET_KEY",
]
