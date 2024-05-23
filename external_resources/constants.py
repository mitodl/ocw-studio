"""Constants for External Resources module"""

# HTTP Status Codes
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_PAYMENT_REQUIRED = 402
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429
HTTP_REQUEST_TIMEOUT = 408
HTTP_SERVICE_UNAVAILABLE = 503

# External Resource
RESOURCE_BROKEN_STATUS_START = HTTP_BAD_REQUEST
RESOURCE_BROKEN_STATUS_END = 600
RESOURCE_UNCHECKED_STATUSES = [
    HTTP_UNAUTHORIZED,
    HTTP_PAYMENT_REQUIRED,
    HTTP_FORBIDDEN,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_REQUEST_TIMEOUT,
    HTTP_SERVICE_UNAVAILABLE,
]

# Celery Task
EXTERNAL_RESOURCE_TASK_RATE_LIMIT = "100/s"
EXTERNAL_RESOURCE_TASK_PRIORITY = 0  # Lowest priority from range (0 - 4)