"""Videos Exceptions"""

from rest_framework import status
from rest_framework.exceptions import APIException


class BadRequest(APIException):
    """Exception for invalid request data"""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Bad request."
    default_code = "bad_request"
