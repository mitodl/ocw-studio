"""Constants for External Resources module"""

from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_403_FORBIDDEN,
    HTTP_408_REQUEST_TIMEOUT,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_503_SERVICE_UNAVAILABLE,
)

# constants for external resources
RESOURCE_BROKEN_STATUS_START = HTTP_400_BAD_REQUEST
RESOURCE_BROKEN_STATUS_END = 600
RESOURCE_UNCHECKED_STATUSES = [
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_403_FORBIDDEN,
    HTTP_408_REQUEST_TIMEOUT,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_503_SERVICE_UNAVAILABLE,
]

# constants for Celery task
EXTERNAL_RESOURCE_TASK_RATE_LIMIT = "100/s"
EXTERNAL_RESOURCE_TASK_PRIORITY = 4  # Lowest priority from range (0 - 4)

# constants for user agent
USER_AGENT_STRING = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 "
    "Safari/537.36"
)

USER_AGENT_TIMEOUT = 30

# metadata fields
METADATA_IS_BROKEN = "is_broken"
METADATA_URL_STATUS_CODE = "url_status_code"
METADATA_BACKUP_URL_STATUS_CODE = "backup_url_status_code"
