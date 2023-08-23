"""
Django settings for ocw_studio.
"""
import logging
import os
import platform
from urllib.parse import urlparse

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from mitol.common.envs import (
    get_bool,
    get_delimited_list,
    get_features,
    get_int,
    get_site_name,
    get_string,
    import_settings_modules,
    init_app_settings,
)

from main.constants import PRODUCTION_NAMES
from main.sentry import init_sentry


# pylint: disable=too-many-lines

VERSION = "0.100.0"

SITE_ID = get_int(
    name="OCW_STUDIO_SITE_ID",
    default=1,
    description="The default site id for django sites framework",
)

# Sentry
ENVIRONMENT = get_string(
    name="OCW_STUDIO_ENVIRONMENT",
    default="dev",
    description="The execution environment that the app is in (e.g. dev, staging, prod)",
    required=True,
)
# this is only available to heroku review apps
HEROKU_APP_NAME = get_string(
    name="HEROKU_APP_NAME", default=None, description="The name of the review app"
)

# initialize Sentry before doing anything else so we capture any config errors
SENTRY_DSN = get_string(
    name="SENTRY_DSN", default="", description="The connection settings for Sentry"
)
SENTRY_LOG_LEVEL = get_string(
    name="SENTRY_LOG_LEVEL", default="ERROR", description="The log level for Sentry"
)
init_sentry(
    dsn=SENTRY_DSN,
    environment=ENVIRONMENT,
    version=VERSION,
    log_level=SENTRY_LOG_LEVEL,
    heroku_app_name=HEROKU_APP_NAME,
)

init_app_settings(namespace="OCW_STUDIO", site_name="OCW Studio")
SITE_NAME = get_site_name()

import_settings_modules(
    "mitol.common.settings.base",
    "mitol.common.settings.webpack",
    "mitol.mail.settings.email",
    "mitol.authentication.settings.touchstone",
)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_string(
    name="SECRET_KEY", default=None, description="Django secret key.", required=True
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = get_bool(
    name="DEBUG",
    default=False,
    dev_only=True,
    description="Set to True to enable DEBUG mode. Don't turn on in production.",
)

ALLOWED_HOSTS = ["*"]

SECURE_SSL_REDIRECT = get_bool(
    name="OCW_STUDIO_SECURE_SSL_REDIRECT",
    default=True,
    description="Application-level SSL redirect setting.",
)


USE_X_FORWARDED_HOST = get_bool(
    name="USE_X_FORWARDED_HOST",
    default=False,
    description="Set HOST header to original domain accessed by user",
)
USE_X_FORWARDED_PORT = get_bool(
    name="USE_X_FORWARDED_PORT",
    default=False,
    description="Use the PORT from original url accessed by user",
)

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
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "guardian",
    "hijack",
    "hijack.contrib.admin",
    "safedelete",
    # django-robots
    "rest_framework",
    "social_django",
    "robots",
    "anymail",
    "bulk_update_or_create",
    # Put our apps after this point
    "main",
    "users",
    "websites",
    "ocw_import",
    "news",
    "content_sync",
    "gdrive_sync",
    "videos",
    # common apps, need to be after ocw-studio apps for template overridding
    "mitol.common.apps.CommonApp",
    "mitol.authentication.apps.AuthenticationApp",
    "mitol.mail.apps.MailApp",
]

if ENVIRONMENT not in PRODUCTION_NAMES:
    INSTALLED_APPS.append("localdev")

DISABLE_WEBPACK_LOADER_STATS = get_bool(
    name="DISABLE_WEBPACK_LOADER_STATS",
    default=False,
    description="Disabled webpack loader stats",
)
if not DISABLE_WEBPACK_LOADER_STATS:
    INSTALLED_APPS.append("webpack_loader")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.sites.middleware.CurrentSiteMiddleware",
    "main.middleware.CachelessAPIMiddleware",
    "hijack.middleware.HijackUserMiddleware",
]

# enable the nplusone profiler only in debug mode
if DEBUG:
    INSTALLED_APPS.append("nplusone.ext.django")
    MIDDLEWARE.append("nplusone.ext.django.NPlusOneMiddleware")

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/"
LOGIN_ERROR_URL = "/"

ROOT_URLCONF = "main.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [f"{BASE_DIR}/templates"],
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
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases
DEFAULT_DATABASE_CONFIG = dj_database_url.parse(
    get_string(
        name="DATABASE_URL",
        default=f"sqlite:///{os.path.join(BASE_DIR, 'db.sqlite3')}",
        description="The connection url to the Postgres database",
        required=True,
        write_app_json=False,
    )
)
DEFAULT_DATABASE_CONFIG["CONN_MAX_AGE"] = get_int(
    name="OCW_STUDIO_DB_CONN_MAX_AGE",
    default=0,
    description="Maximum age of connection to Postgres in seconds",
)
# If True, disables server-side database cursors to prevent invalid cursor errors when using pgbouncer
DEFAULT_DATABASE_CONFIG["DISABLE_SERVER_SIDE_CURSORS"] = get_bool(
    name="OCW_STUDIO_DB_DISABLE_SS_CURSORS",
    default=True,
    description="Disables Postgres server side cursors",
)

if get_bool(
    name="OCW_STUDIO_DB_DISABLE_SSL",
    default=False,
    description="Disables SSL to postgres if set to True",
):
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
ROBOTS_CACHE_TIMEOUT = get_int(
    name="ROBOTS_CACHE_TIMEOUT",
    default=60 * 60 * 24,
    description="How long the robots.txt file should be cached",
)

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

# Serve static files with dj-static
STATIC_URL = "/static/"
STATIC_ROOT = "staticfiles"
STATICFILES_DIRS = (os.path.join(BASE_DIR, "static"),)

# Important to define this so DEBUG works properly
INTERNAL_IPS = (
    get_string(
        name="HOST_IP", default="127.0.0.1", description="This server's host IP"
    ),
)

# e-mail configurable admins
ADMIN_EMAIL = get_string(
    name="OCW_STUDIO_ADMIN_EMAIL",
    default="",
    description="E-mail to send 500 reports to.",
)
if ADMIN_EMAIL != "":
    ADMINS = (("Admins", ADMIN_EMAIL),)
else:
    ADMINS = ()

# Logging configuration
LOG_LEVEL = get_string(
    name="OCW_STUDIO_LOG_LEVEL", default="INFO", description="The log level default"
)
DJANGO_LOG_LEVEL = get_string(
    name="DJANGO_LOG_LEVEL", default="INFO", description="The log level for django"
)
# For logging to a remote syslog host
LOG_HOST = get_string(
    name="OCW_STUDIO_LOG_HOST",
    default="localhost",
    description="Remote syslog server hostname",
)
LOG_HOST_PORT = get_int(
    name="OCW_STUDIO_LOG_HOST_PORT",
    default=514,
    description="Remote syslog server port",
)

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
                f"[{HOSTNAME}] - %(message)s"
            ),
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
STATUS_TOKEN = get_string(
    name="STATUS_TOKEN", default="", description="Token to access the status API."
)
HEALTH_CHECK = ["CELERY", "REDIS", "POSTGRES"]

GA_TRACKING_ID = get_string(
    name="GA_TRACKING_ID", default="", description="Google analytics tracking ID"
)
REACT_GA_DEBUG = get_bool(
    name="REACT_GA_DEBUG",
    default=False,
    dev_only=True,
    description="Enable debug for react-ga, development only",
)

MEDIA_ROOT = get_string(
    name="MEDIA_ROOT",
    default="/var/media/",
    description="The root directory for locally stored media. Typically not used.",
)
MEDIA_URL = "/media/"
OCW_STUDIO_USE_S3 = get_bool(
    name="OCW_STUDIO_USE_S3",
    default=False,
    description="Use S3 for storage backend (required on Heroku)",
)
MAX_S3_GET_ITERATIONS = get_int(
    name="MAX_S3_GET_ITERATIONS",
    default=3,
    description="Max retry attempts to get an S3 object",
)
AWS_ACCESS_KEY_ID = get_string(
    name="AWS_ACCESS_KEY_ID", default=None, description="AWS Access Key for S3 storage."
)
AWS_SECRET_ACCESS_KEY = get_string(
    name="AWS_SECRET_ACCESS_KEY",
    default=None,
    description="AWS Secret Key for S3 storage.",
)
AWS_STORAGE_BUCKET_NAME = get_string(
    name="AWS_STORAGE_BUCKET_NAME", default=None, description="S3 Bucket name."
)
AWS_PREVIEW_BUCKET_NAME = get_string(
    name="AWS_PREVIEW_BUCKET_NAME", default=None, description="S3 preview bucket name."
)
AWS_PUBLISH_BUCKET_NAME = get_string(
    name="AWS_PUBLISH_BUCKET_NAME", default=None, description="S3 publish bucket name."
)
AWS_OFFLINE_PREVIEW_BUCKET_NAME = get_string(
    name="AWS_OFFLINE_PREVIEW_BUCKET_NAME",
    default=None,
    description="S3 offline preview bucket name.",
)
AWS_OFFLINE_PUBLISH_BUCKET_NAME = get_string(
    name="AWS_OFFLINE_PUBLISH_BUCKET_NAME",
    default=None,
    description="S3 offline publish bucket name.",
)
AWS_QUERYSTRING_AUTH = get_bool(
    name="AWS_QUERYSTRING_AUTH",
    default=False,
    description="Enables querystring auth for S3 urls",
)
AWS_DEFAULT_ACL = "public-read"
AWS_ACCOUNT_ID = get_string(name="AWS_ACCOUNT_ID", description="AWS Account ID")
AWS_REGION = get_string(
    name="AWS_REGION", default="us-east-1", description="AWS Region"
)
AWS_ROLE_NAME = get_string(
    name="AWS_ROLE_NAME",
    default=None,
    description="AWS role name to be used for MediaConvert jobs",
)

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


# Google Drive and Video settings
DRIVE_SERVICE_ACCOUNT_CREDS = get_string(
    name="DRIVE_SERVICE_ACCOUNT_CREDS",
    default=None,
    description="The contents of the Service Account credentials JSON to use for Google API auth",
)
DRIVE_SHARED_ID = get_string(
    name="DRIVE_SHARED_ID",
    default=None,
    description="ID of the Shared Drive (a.k.a. Team Drive). This is equal to the top-level folder ID.",
)
DRIVE_S3_UPLOAD_PREFIX = get_string(
    name="DRIVE_S3_UPLOAD_PREFIX",
    default="gdrive_uploads",
    description=("Prefix to be used for S3 keys of files uploaded from Google Drive"),
)
DRIVE_UPLOADS_PARENT_FOLDER_ID = get_string(
    name="DRIVE_UPLOADS_PARENT_FOLDER_ID",
    default=None,
    description="Gdrive folder for video uploads",
    required=False,
)
OCW_NEXT_SEARCH_WEBHOOK_KEY = get_string(
    name="OCW_NEXT_SEARCH_WEBHOOK_KEY",
    default="",
    description="Open discussions webhook key",
    required=False,
)
OPEN_DISCUSSIONS_URL = get_string(
    name="OPEN_DISCUSSIONS_URL",
    default="",
    description="Open discussions url",
    required=False,
)
VIDEO_S3_TRANSCODE_PREFIX = get_string(
    name="VIDEO_S3_TRANSCODE_PREFIX",
    default="aws_mediaconvert_transcodes",
    description=(
        "Prefix to be used for S3 keys of files transcoded from AWS MediaConvert"
    ),
)
VIDEO_S3_TRANSCODE_ENDPOINT = get_string(
    name="VIDEO_S3_TRANSCODE_ENDPOINT",
    default="aws_mediaconvert_transcodes",
    description=("Endpoint to be used for AWS MediaConvert"),
)
VIDEO_TRANSCODE_QUEUE = get_string(
    name="VIDEO_TRANSCODE_QUEUE",
    default="Default",
    description=("Name of MediaConvert queue to use for transcoding"),
)
YT_ACCESS_TOKEN = get_string(
    name="YT_ACCESS_TOKEN", default="", description="Youtube access token"
)
YT_CATEGORY_ID = get_int(
    name="YT_CATEGORY_ID",
    default=27,
    description="Default video category ID for youtube",
)
YT_CLIENT_ID = get_string(
    name="YT_CLIENT_ID", default="", description="Youtube Client ID"
)
YT_CLIENT_SECRET = get_string(
    name="YT_CLIENT_SECRET", default="", description="Youtube client secret key"
)
YT_REFRESH_TOKEN = get_string(
    name="YT_REFRESH_TOKEN", default="", description="YT_REFRESH_TOKEN"
)
YT_PROJECT_ID = get_string(
    name="YT_PROJECT_ID", default="", description="Youtube project ID"
)
YT_STATUS_UPDATE_FREQUENCY = get_int(
    name="YT_STATUS_UPDATE_FREQUENCY",
    default=60,
    description="The frequency to check for status updates on uploaded youtube videos",
)
YT_UPLOAD_FREQUENCY = get_int(
    name="YT_UPLOAD_FREQUENCY",
    default=60,
    description="The frequency to check for videos to upload to Youtube",
)
YT_UPLOAD_LIMIT = get_int(
    name="YT_UPLOAD_LIMIT",
    default=50,
    description="Max Youtube uploads allowed per day",
)
# OCW metadata fields
FIELD_RESOURCETYPE = get_string(
    name="FIELD_RESOURCETYPE",
    default="resourcetype",
    description="The site config metadata field for the resource type",
)
FIELD_METADATA_TITLE = get_string(
    name="FIELD_METADATA_TITLE",
    default="course_title",
    description="The site metadata field for title",
)
# YouTube OCW metadata fields
YT_FIELD_CAPTIONS = get_string(
    name="YT_FIELD_CAPTIONS",
    default="video_files.video_captions_file",
    description="The site config metadata field for the caption url",
)
YT_FIELD_ID = get_string(
    name="YT_FIELD_ID",
    default="video_metadata.youtube_id",
    description="The site config metadata field for YouTube ID",
)
YT_FIELD_DESCRIPTION = get_string(
    name="YT_FIELD_DESCRIPTION",
    default="video_metadata.youtube_description",
    description="The site config metadata field for YouTube description",
)
YT_FIELD_SPEAKERS = get_string(
    name="YT_FIELD_SPEAKERS",
    default="video_metadata.video_speakers",
    description="The site config metadata field for YouTube speakers",
)
YT_FIELD_TAGS = get_string(
    name="YT_FIELD_TAGS",
    default="video_metadata.video_tags",
    description="The site config metadata field for YouTube video tags",
)
YT_FIELD_THUMBNAIL = get_string(
    name="YT_FIELD_THUMBNAIL",
    default="video_files.video_thumbnail_file",
    description="The site config metadata field for YouTube thumbnail url",
)
YT_FIELD_TRANSCRIPT = get_string(
    name="YT_FIELD_TRANSCRIPT",
    default="video_files.video_transcript_file",
    description="The site config metadata field for the transcript url",
)


UPDATE_TAGGED_3PLAY_TRANSCRIPT_FREQUENCY = get_int(
    name="UPDATE_TAGGED_3PLAY_TRANSCRIPT_FREQUENCY",
    default=3600,
    description="The frequency to check for videos tagged as updated in 3play",
)

UPDATE_MISSING_TRANSCRIPT_FREQUENCY = get_int(
    name="UPDATE_MISSING_TRANSCRIPT_FREQUENCY",
    default=43200,
    description="The frequency to check for transcripts for published videos with blank transcripts",
)

# Publish status settings
PUBLISH_STATUS_WAIT_TIME = get_int(
    name="PUBLISH_STATUS_WAIT_TIME",
    default=600,
    description="Number of seconds to wait for a publish status update before querying for it via api",
    required=False,
)
PUBLISH_STATUS_CUTOFF = get_int(
    name="PUBLISH_STATUS_CUTOFF",
    default=1800,
    description="Number of seconds to wait for a publish build to fail/succeed before assuming it's stuck",
    required=False,
)
PUBLISH_INCOMPLETE_BUILD_STATUS_FREQUENCY = get_int(
    name="PUBLISH_INCOMPLETE_BUILD_STATUS_FREQUENCY",
    default=1800,
    description="Frequency (in seconds) to run a check on potentially stalled publish builds",
    required=False,
)


# Celery
REDISCLOUD_URL = get_string(
    name="REDISCLOUD_URL", default=None, description="RedisCloud connection url"
)
if REDISCLOUD_URL is not None:
    _redis_url = REDISCLOUD_URL
else:
    _redis_url = get_string(
        name="REDIS_URL", default=None, description="Redis URL for non-production use"
    )
REDIS_MAX_CONNECTIONS = get_int(
    name="REDIS_MAX_CONNECTIONS",
    default=48,
    description="Max number of redis connections",
)
DJANGO_REDIS_CLOSE_CONNECTION = True

CELERY_BROKER_URL = get_string(
    name="CELERY_BROKER_URL",
    default=_redis_url,
    description="Where celery should get tasks, default is Redis URL",
)
CELERY_RESULT_BACKEND = get_string(
    name="CELERY_RESULT_BACKEND",
    default=_redis_url,
    description="Where celery should put task results, default is Redis URL",
)
CELERY_TASK_ALWAYS_EAGER = get_bool(
    name="CELERY_TASK_ALWAYS_EAGER",
    default=False,
    dev_only=True,
    description="Enables eager execution of celery tasks, development only",
)
CELERY_TASK_EAGER_PROPAGATES = get_bool(
    name="CELERY_TASK_EAGER_PROPAGATES",
    default=True,
    description="Early executed tasks propagate exceptions",
)

CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"

CELERY_BEAT_SCHEDULE = {
    "update-youtube-statuses": {
        "task": "videos.tasks.update_youtube_statuses",
        "schedule": YT_STATUS_UPDATE_FREQUENCY,
    },
    "upload-youtube-videos": {
        "task": "videos.tasks.upload_youtube_videos",
        "schedule": YT_UPLOAD_FREQUENCY,
    },
    "update-transcripts-for-updated-videos": {
        "task": "videos.tasks.update_transcripts_for_updated_videos",
        "schedule": UPDATE_TAGGED_3PLAY_TRANSCRIPT_FREQUENCY,
    },
    "attempt-to-update-missing-transcripts": {
        "task": "videos.tasks.attempt_to_update_missing_transcripts",
        "schedule": UPDATE_MISSING_TRANSCRIPT_FREQUENCY,
    },
    "check_incomplete_publish_build_statuses": {
        "task": "content_sync.tasks.check_incomplete_publish_build_statuses",
        "schedule": PUBLISH_INCOMPLETE_BUILD_STATUS_FREQUENCY,
    },
}

# django cache back-ends
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "local-in-memory-cache",
    },
    "redis": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": CELERY_BROKER_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": REDIS_MAX_CONNECTIONS},
        },
    },
}


FEATURES_DEFAULT = get_bool(
    name="FEATURES_DEFAULT",
    default=False,
    dev_only=True,
    description="The default value for all feature flags",
)
FEATURES = get_features()

MIDDLEWARE_FEATURE_FLAG_QS_PREFIX = get_string(
    name="MIDDLEWARE_FEATURE_FLAG_QS_PREFIX",
    default=None,
    description="Feature flag middleware querystring prefix",
)
MIDDLEWARE_FEATURE_FLAG_COOKIE_NAME = get_string(
    name="MIDDLEWARE_FEATURE_FLAG_COOKIE_NAME",
    default="OCW_STUDIO_FEATURE_FLAGS",
    description="Feature flag middleware cookie name",
)
MIDDLEWARE_FEATURE_FLAG_COOKIE_MAX_AGE_SECONDS = get_int(
    name="MIDDLEWARE_FEATURE_FLAG_COOKIE_MAX_AGE_SECONDS",
    default=60 * 60,
    description="Feature flag middleware cookie max age",
)

if MIDDLEWARE_FEATURE_FLAG_QS_PREFIX:
    MIDDLEWARE.append(
        [
            "main.middleware.QueryStringFeatureFlagMiddleware",
            "main.middleware.CookieFeatureFlagMiddleware",
        ]
    )

THREEPLAY_API_KEY = get_string(
    name="THREEPLAY_API_KEY",
    default=None,
    description="3play api key",
)

THREEPLAY_CALLBACK_KEY = get_string(
    name="THREEPLAY_CALLBACK_KEY",
    default=None,
    description="3play callback key",
)

THREEPLAY_PROJECT_ID = get_int(
    name="THREEPLAY_PROJECT_ID",
    default=2,
    description="3play project id",
)

S3_TRANSCRIPTS_PREFIX = get_string(
    name="S3_TRANSCRIPTS_PREFIX",
    default="transcript_files",
    description="s3 transcripts subfolder",
)

# django debug toolbar only in debug mode
if DEBUG:
    INSTALLED_APPS.append("debug_toolbar")
    # it needs to be enabled before other middlewares
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")


AUTHENTICATION_BACKENDS = (
    "social_core.backends.saml.SAMLAuth",
    "django.contrib.auth.backends.ModelBackend",  # this is default
    "guardian.backends.ObjectPermissionBackend",
)

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

HIJACK_LOGIN_REDIRECT_URL = "sites"
HIJACK_LOGOUT_REDIRECT_URL = "/admin/users/user/"
HIJACK_REGISTER_ADMIN = False
HIJACK_ALLOW_GET_REQUESTS = True

LOGOUT_URL = "/logout"
LOGOUT_REDIRECT_URL = "/"

SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.social_auth.associate_by_email",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
)
SOCIAL_AUTH_LOGIN_REDIRECT_URL = "sites"
SOCIAL_AUTH_LOGIN_ERROR_URL = "main-index"
SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS = [
    urlparse(SITE_BASE_URL).netloc  # pylint: disable=undefined-variable
]

SOCIAL_AUTH_USER_FIELD_MAPPING = {"fullname": "name"}

# SAML backend settings
SOCIAL_AUTH_SAML_LOGIN_URL = get_string(
    name="SOCIAL_AUTH_SAML_LOGIN_URL",
    default=None,
    description="The URL to redirect the user to for SAML login",
    required=True,
)

CONTENT_SYNC_BACKEND = get_string(
    name="CONTENT_SYNC_BACKEND",
    default=None,
    description="The backend to sync websites/content with",
    required=False,
)
CONTENT_SYNC_RETRIES = get_int(
    name="CONTENT_SYNC_RETRIES",
    default=5,
    description="Number of times to retry backend sync attempts",
    required=False,
)
CONTENT_SYNC_PIPELINE_BACKEND = get_string(
    name="CONTENT_SYNC_PIPELINE_BACKEND",
    default="concourse",
    description="The pipeline backend name to preview/publish websites with",
    required=False,
)

# Concourse-CI settings
CONCOURSE_URL = get_string(
    name="CONCOURSE_URL",
    default=None,
    description="The concourse-ci URL",
    required=False,
)
CONCOURSE_USERNAME = get_string(
    name="CONCOURSE_USERNAME",
    default=None,
    description="The concourse-ci login username",
    required=False,
)
CONCOURSE_PASSWORD = get_string(
    name="CONCOURSE_PASSWORD",
    default=None,
    description="The concourse-ci login password",
    required=False,
)
CONCOURSE_TEAM = get_string(
    name="CONCOURSE_TEAM",
    default="ocw",
    description="The concourse-ci team",
    required=False,
)
CONCOURSE_HARD_PURGE = get_bool(
    name="CONCOURSE_HARD_PURGE",
    default=True,
    description="Perform a hard purge of the fastly cache",
    required=False,
)
CONCOURSE_IS_PRIVATE_REPO = get_bool(
    name="CONCOURSE_IS_PRIVATE_REPO",
    default=True,
    description="True if a git repo requires authentication to retrieve",
    required=False,
)
# Git backend settings
GIT_TOKEN = get_string(
    name="GIT_TOKEN",
    default=None,
    description="An authentication token for git commands",
    required=False,
)
GITHUB_APP_ID = get_int(
    name="GITHUB_APP_ID",
    default=None,
    description="A github app id to use for Github API authentication",
    required=False,
)
GITHUB_APP_PRIVATE_KEY = (
    get_string(
        name="GITHUB_APP_PRIVATE_KEY",
        default="",
        description="A github app private key for authentication",
        required=False,
    )
    .encode()
    .decode("unicode_escape")
    .encode()
)
GIT_ORGANIZATION = get_string(
    name="GIT_ORGANIZATION",
    default=None,
    description="The organization under which repos should be created",
    required=False,
)
GIT_BRANCH_MAIN = get_string(
    name="GIT_BRANCH_MAIN",
    default="main",
    description="The default branch for a git repo",
    required=False,
)
GIT_BRANCH_PREVIEW = get_string(
    name="GIT_BRANCH_PREVIEW",
    default="preview",
    description="The preview branch for a git repo",
    required=False,
)
GIT_BRANCH_RELEASE = get_string(
    name="GIT_BRANCH_RELEASE",
    default="release",
    description="The release branch for a git repo",
    required=False,
)
GIT_DEFAULT_USER_NAME = get_string(
    name="GIT_DEFAULT_USER_NAME",
    default="Anonymous",
    description="The name for the default git committer",
    required=False,
)
GIT_DEFAULT_USER_EMAIL = get_string(
    name="GIT_DEFAULT_USER_EMAIL",
    default="anonymous@example.edu",
    description="The email for the default git committer",
    required=False,
)
GIT_API_URL = get_string(
    name="GIT_API_URL",
    default=None,
    description="Base URL of git API",
    required=False,
)
GIT_DOMAIN = get_string(
    name="GIT_DOMAIN",
    default="www.github.com",
    description="Base URL of github for site repos",
    required=False,
)
GITHUB_WEBHOOK_KEY = get_string(
    name="GITHUB_WEBHOOK_KEY",
    default="",
    description="Github secret key sent by webhook requests",
    required=False,
)
GITHUB_WEBHOOK_BRANCH = get_string(
    name="GITHUB_WEBHOOK_BRANCH",
    default="",
    description="Github branch to filter webhook requests against",
    required=False,
)
GITHUB_RATE_LIMIT_CHECK = get_bool(
    name="GITHUB_RATE_LIMIT_CHECK",
    default=False,
    description="True if the github domain has API rate limits",
    required=False,
)
GITHUB_RATE_LIMIT_CUTOFF = get_int(
    name="GITHUB_RATE_LIMIT_CUTOFF",
    default=100,
    description="Number of remaining Github API calls that triggers throttling",
    required=False,
)
GITHUB_RATE_LIMIT_MIN_SLEEP = get_int(
    name="GITHUB_RATE_LIMIT_MIN_SLEEP",
    default=5,
    description="Minimum time to sleep between when throttling github calls",
    required=False,
)
OCW_IMPORT_STARTER_SLUG = get_string(
    name="OCW_IMPORT_STARTER_SLUG",
    default="course",
    description="The slug of the WebsiteStarter to assign to courses imported from ocw-to-hugo",
    required=False,
)
OCW_COURSE_STARTER_SLUG = get_string(
    name="OCW_COURSE_STARTER_SLUG",
    default="course",
    description="The slug of the WebsiteStarter currently used for OCW course sites",
    required=False,
)
OCW_GTM_ACCOUNT_ID = get_string(
    name="OCW_GTM_ACCOUNT_ID",
    default=None,
    description="The Google Tag Manager account ID to use in OCW site build pipelines",
)
OCW_STUDIO_SITE_CONFIG_FILE = get_string(
    name="OCW_STUDIO_SITE_CONFIG_FILE",
    default="ocw-studio.yaml",
    description="Standard file name for site config files",
    required=False,
)
OCW_MASS_BUILD_BATCH_SIZE = get_int(
    name="OCW_STUDIO_MASS_BUILD_BATCH_SIZE",
    default=20,
    description="The amount of site builds per job to put in MassBuildSitesPipelineDefinition",
    required=False,
)
OCW_MASS_BUILD_MAX_IN_FLIGHT = get_int(
    name="OCW_MASS_BUILD_MAX_IN_FLIGHT",
    default=10,
    description="The amount of sites to build simultaneously in each job created by MassBuildSitesPipelineDefinition"
)

ROOT_WEBSITE_NAME = get_string(
    name="ROOT_WEBSITE_NAME",
    default="ocw-www",
    description="The Website name for the site at the root domain",
    required=False,
)

API_BEARER_TOKEN = get_string(
    name="API_BEARER_TOKEN",
    default=None,
    description="Authorization bearer token for webhook endpoints",
    required=False,
)

# mitol-django-mail
MAILGUN_SENDER_DOMAIN = get_string(
    name="MAILGUN_SENDER_DOMAIN",
    default=None,
    description="The domain to send mailgun email through",
    required=True,
)
MAILGUN_KEY = get_string(
    name="MAILGUN_KEY",
    default=None,
    description="The token for authenticating against the Mailgun API",
    required=True,
)
ANYMAIL = {
    "MAILGUN_API_KEY": MAILGUN_KEY,
    "MAILGUN_SENDER_DOMAIN": MAILGUN_SENDER_DOMAIN,
}
MITOL_MAIL_FROM_EMAIL = get_string(
    name="MITOL_MAIL_FROM_EMAIL",
    default="webmaster@localhost",
    description="E-mail to use for the from field",
)
MITOL_MAIL_REPLY_TO_ADDRESS = get_string(
    name="MITOL_MAIL_REPLY_TO_ADDRESS",
    default="webmaster@localhost",
    description="E-mail to use for reply-to address of emails",
)
MITOL_MAIL_MESSAGE_CLASSES = [
    "videos.messages.YouTubeUploadSuccessMessage",
    "videos.messages.YouTubeUploadFailureMessage",
    "websites.messages.PreviewOrPublishSuccessMessage",
    "websites.messages.PreviewOrPublishFailureMessage",
    "websites.messages.videoTranscriptingCompleteMessage",
]
MITOL_MAIL_RECIPIENT_OVERRIDE = get_string(
    name="MITOL_MAIL_RECIPIENT_OVERRIDE",
    default=None,
    dev_only=True,
    description="Override the recipient for outgoing email, development only",
)
MITOL_MAIL_ENABLE_EMAIL_DEBUGGER = get_bool(
    name="MITOL_MAIL_ENABLE_EMAIL_DEBUGGER",
    default=DEBUG,
    description="Enable the mitol-mail email debugger",
    dev_only=True,
)
MITOL_MAIL_FORMAT_RECIPIENT_FUNC = get_string(
    name="MITOL_MAIL_FORMAT_RECIPIENT_FUNC",
    default="users.utils.format_recipient",
    description="function to format email recipients",
)
OCW_STUDIO_DRAFT_URL = get_string(
    name="OCW_STUDIO_DRAFT_URL",
    default=None,
    description="The base url of the preview site",
)
OCW_STUDIO_LIVE_URL = get_string(
    name="OCW_STUDIO_LIVE_URL",
    default=None,
    description="The base url of the live site",
)
PREPUBLISH_ACTIONS = get_delimited_list(
    name="PREPUBLISH_ACTIONS",
    default=[],
    description="Actions to perform before publish",
)
SEARCH_API_URL = get_string(
    name="SEARCH_API_URL",
    default=None,
    description="The URL to open discussions search to inject into the theme assets build",
)
STATIC_API_BASE_URL = get_string(
    name="STATIC_API_BASE_URL",
    description="The static api base url to use when building and deploying sites locally to minio",
    default="",
    required=False,
    dev_only=True,
)
RESOURCE_BASE_URL_DRAFT = get_string(
    name="RESOURCE_BASE_URL_DRAFT",
    description="The draft resource base url to use when building and deploying sites locally to minio",
    default="",
    required=False,
    dev_only=True,
)
RESOURCE_BASE_URL_LIVE = get_string(
    name="RESOURCE_BASE_URL_LIVE",
    description="The live resource base url to use when building and deploying sites locally to minio",
    default="",
    required=False,
    dev_only=True,
)
OCW_HUGO_THEMES_BRANCH = get_string(
    name="OCW_HUGO_THEMES_BRANCH",
    description="The branch to use in development of ocw-hugo-themes",
    required=False,
    dev_only=True,
)
OCW_HUGO_PROJECTS_BRANCH = get_string(
    name="OCW_HUGO_PROJECTS_BRANCH",
    description="The branch to use in development of ocw-hugo-projects",
    required=False,
    dev_only=True,
)
RESOURCE_TYPE_FIELDS = get_delimited_list(
    name="RESOURCE_TYPE_FIELDS",
    default=["resourcetype", "filetype"],
    description="List of site configuration fields that are used to store resource type",
)
SITEMAP_DOMAIN = get_string(
    name="SITEMAP_DOMAIN",
    default="ocw.mit.edu",
    description="The domain to be used in Hugo builds for fully qualified URLs in the sitemap",
)
OCW_HUGO_THEMES_SENTRY_DSN = get_string(
    name="OCW_HUGO_THEMES_SENTRY_DSN",
    required=False,
    description="The sentry DSN that will be used in ocw-hugo-themes",
)
ENV_NAME = get_string(
    name="ENV_NAME",
    default="rc",
    description="Name of environment from Heroku or other deployment",
    required=False,
)
