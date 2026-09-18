"""Tests for s3_utils"""

import pytest

from main.s3_utils import get_boto3_options, get_s3_object_and_read


@pytest.mark.parametrize("iterations", [1, 2, 5])
def test_s3_object_and_read(settings, mocker, iterations):
    """
    Test that s3_object_and_read is retried on error up to max number of iterations
    """
    settings.MAX_S3_GET_ITERATIONS = iterations
    mock_s3_object = mocker.Mock()
    with pytest.raises(Exception):  # noqa: B017, PT011
        get_s3_object_and_read(mock_s3_object)
    assert mock_s3_object.get.call_count == iterations + 1


def test_boto3_options_use_configured_endpoint(settings):
    """AWS_S3_ENDPOINT_URL should override the compose-era default"""
    settings.ENVIRONMENT = "dev"
    settings.AWS_S3_ENDPOINT_URL = "http://rustfs.local-infra.svc.cluster.local:9000"
    assert (
        get_boto3_options()["endpoint_url"]
        == "http://rustfs.local-infra.svc.cluster.local:9000"
    )


def test_boto3_options_dev_fallback(settings):
    """Without AWS_S3_ENDPOINT_URL, dev still points at the compose Minio IP"""
    settings.ENVIRONMENT = "dev"
    settings.AWS_S3_ENDPOINT_URL = None
    assert get_boto3_options()["endpoint_url"] == "http://10.1.0.100:9000"


def test_boto3_options_endpoint_outside_dev(settings):
    """A configured endpoint applies in any environment, not just dev"""
    settings.ENVIRONMENT = "production"
    settings.AWS_S3_ENDPOINT_URL = "https://s3.example.test"
    assert get_boto3_options()["endpoint_url"] == "https://s3.example.test"


def test_boto3_options_no_endpoint_outside_dev(settings):
    """Non-dev environments with no override talk to real AWS"""
    settings.ENVIRONMENT = "production"
    settings.AWS_S3_ENDPOINT_URL = None
    assert "endpoint_url" not in get_boto3_options()
