""" Tests for s3_utils """

import pytest

from main.s3_utils import get_s3_object_and_read


@pytest.mark.parametrize("iterations", [1, 2, 5])
def test_s3_object_and_read(settings, mocker, iterations):
    """
    Test that s3_object_and_read is retried on error up to max number of iterations
    """
    settings.MAX_S3_GET_ITERATIONS = iterations
    mock_s3_object = mocker.Mock()
    with pytest.raises(Exception):
        get_s3_object_and_read(mock_s3_object)
    assert mock_s3_object.get.call_count == iterations + 1
