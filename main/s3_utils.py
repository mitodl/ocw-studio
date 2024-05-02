"""S3 utility functions"""

import boto3
from django.conf import settings


def get_boto3_options(extra_options=None):
    """
    Provides default boto3 options, connecting to Minio if the environment is dev

    Args:
        extra_options (dict): (Optional) Extra options to append

    Returns:
        dict: A dictionary of options to initialize an s3 resource or client with
    """  # noqa: D401
    options = {
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
    }
    if settings.ENVIRONMENT == "dev":
        options.update({"endpoint_url": "http://10.1.0.100:9000"})
    if extra_options:
        options.update(extra_options)
    return options


def get_boto3_resource(service_type, extra_options=None):
    """
    Provides an S3 resource

    Args:
        service_type (string): The AWS service_type to initialize the resource with
        extra_options (dict): (Optional) Extra options to initialize the resource with

    Returns:
        s3.ServiceResource: An S3 resource
    """  # noqa: D401
    return boto3.resource(service_type, **get_boto3_options(extra_options))


def get_boto3_client(service_type, extra_options=None):
    """
    Provides an S3 client

    Args:
        service_type (string): The AWS service_type to initialize the resource with
        extra_options (dict): (Optional) Extra options to initialize the resource with

    Returns:
        s3.Client: An S3 client
    """  # noqa: D401
    return boto3.client(service_type, **get_boto3_options(extra_options))


def get_s3_object_and_read(obj, iteration=0):
    """
    Attempts to read S3 data, and tries again up to MAX_S3_GET_ITERATIONS if it encounters an error.
    This helps to prevent read timeout errors from stopping sync.

    Args:
        obj (s3.ObjectSummary): The S3 ObjectSummary we are trying to read
        iteration (int): A number tracking how many times this function has been run

    Returns:
        bytes: The contents of a json file read from S3
    """  # noqa: D401, E501
    try:
        return obj.get()["Body"].read()
    except Exception:  # pylint: disable=broad-except  # noqa: BLE001
        if iteration < settings.MAX_S3_GET_ITERATIONS:
            return get_s3_object_and_read(obj, iteration + 1)
        else:
            raise
