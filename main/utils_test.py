""" Tests for utils """
from math import ceil

import pytest

from main.utils import chunks, get_s3_object_and_read


def test_chunks():
    """
    test for chunks
    """
    input_list = list(range(113))
    output_list = []
    for nums in chunks(input_list):
        output_list += nums
    assert output_list == input_list

    output_list = []
    for nums in chunks(input_list, chunk_size=1):
        output_list += nums
    assert output_list == input_list

    output_list = []
    for nums in chunks(input_list, chunk_size=124):
        output_list += nums
    assert output_list == input_list


def test_chunks_iterable():
    """
    test that chunks works on non-list iterables too
    """
    count = 113
    input_range = range(count)
    chunk_output = []
    for chunk in chunks(input_range, chunk_size=10):
        chunk_output.append(chunk)
    assert len(chunk_output) == ceil(113 / 10)

    range_list = []
    for chunk in chunk_output:
        range_list += chunk
    assert range_list == list(range(count))


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
