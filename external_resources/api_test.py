"""Tests for External Resources API"""

import pytest
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
)
from requests.exceptions import (
    HTTPError,
    InvalidURL,
    SSLError,
    Timeout,
    TooManyRedirects,
)
from rest_framework.status import HTTP_200_OK

from external_resources.api import (
    check_wayback_jobs_status_batch,
    is_external_url_broken,
    is_url_broken,
    make_wayback_request,
    submit_url_to_wayback,
)
from external_resources.constants import (
    RESOURCE_UNCHECKED_STATUSES,
    USER_AGENT_STRING,
    USER_AGENT_TIMEOUT,
    WAYBACK_API_URL,
    WAYBACK_CHECK_STATUS_URL,
    WAYBACK_HEADERS,
)
from external_resources.exceptions import CheckFailedError


def test_is_url_broken_valid(mocker):
    """Test for working url"""
    mock_response = mocker.Mock(status_code=HTTP_200_OK)
    mocker.patch("external_resources.api.requests.head", return_value=mock_response)

    result, status_code = is_url_broken("http://google.com")
    assert not result
    assert status_code == HTTP_200_OK


@pytest.mark.parametrize("status_code", RESOURCE_UNCHECKED_STATUSES)
def test_is_url_broken_whitelisted(mocker, status_code):
    """Test for broken url"""
    mock_response = mocker.Mock(status_code=status_code)
    mocker.patch("external_resources.api.requests.head", return_value=mock_response)

    result, response_status_code = is_url_broken("http://google.com/")
    assert result
    assert response_status_code == status_code


@pytest.mark.parametrize("url", ["", "   "])
def test_is_url_broken_empty(mocker, url):
    """Test for empty url"""
    mock_head = mocker.patch("external_resources.api.requests.head")

    result, status_code = is_url_broken(url)
    assert not result
    assert status_code is None
    mock_head.assert_not_called()


def test_is_url_broken_request_options(mocker):
    """The check should follow redirects, time out and send a browser user agent"""
    mock_head = mocker.patch(
        "external_resources.api.requests.head",
        return_value=mocker.Mock(status_code=HTTP_200_OK),
    )

    is_url_broken("http://google.com")

    mock_head.assert_called_once_with(
        "http://google.com",
        allow_redirects=True,
        timeout=USER_AGENT_TIMEOUT,
        headers={"Accept": "*/*", "User-Agent": USER_AGENT_STRING},
    )


@pytest.mark.parametrize(
    ("metadata", "expected_url"),
    [({"external_url": "http://google.com"}, "http://google.com"), ({}, "")],
)
def test_is_external_url_broken(mocker, metadata, expected_url):
    """is_external_url_broken should check the external_url of the resource"""
    mock_is_url_broken = mocker.patch(
        "external_resources.api.is_url_broken", return_value=(False, HTTP_200_OK)
    )

    result = is_external_url_broken(mocker.Mock(metadata=metadata))

    assert result == (False, HTTP_200_OK)
    mock_is_url_broken.assert_called_once_with(expected_url)


@pytest.mark.parametrize(
    "error", [RequestsConnectionError, Timeout, SSLError, TooManyRedirects, InvalidURL]
)
def test_is_url_broken_exception(mocker, error):
    """Request errors should be raised as CheckFailedError"""
    mocker.patch(
        "external_resources.api.requests.head",
        side_effect=error,
    )

    with pytest.raises(CheckFailedError) as exc_info:
        is_url_broken("http://google.com")
    assert isinstance(exc_info.value.__cause__, error)


def test_make_wayback_request(mocker):
    """make_wayback_request should post the params and return the response JSON"""
    mock_post = mocker.patch("external_resources.api.requests.post")
    mock_post.return_value.json.return_value = {"job_id": "job_1"}
    params = {"url": "http://google.com"}

    result = make_wayback_request(WAYBACK_API_URL, params, WAYBACK_HEADERS)

    assert result == {"job_id": "job_1"}
    mock_post.assert_called_once_with(
        WAYBACK_API_URL, headers=WAYBACK_HEADERS, data=params, timeout=30
    )
    mock_post.return_value.raise_for_status.assert_called_once_with()


def test_make_wayback_request_logs_message(mocker):
    """A message in the Wayback Machine response should be logged"""
    mock_post = mocker.patch("external_resources.api.requests.post")
    mock_post.return_value.json.return_value = {"message": "Daily limit reached"}
    mock_log = mocker.patch("external_resources.api.log")

    make_wayback_request(WAYBACK_API_URL, {}, WAYBACK_HEADERS)

    mock_log.warning.assert_called_once_with(
        "Wayback Machine response message: %s", "Daily limit reached"
    )


def test_make_wayback_request_http_error(mocker):
    """HTTP errors from the Wayback Machine should be logged and raised"""
    mock_post = mocker.patch("external_resources.api.requests.post")
    mock_post.return_value.json.return_value = {}
    mock_post.return_value.raise_for_status.side_effect = HTTPError
    mock_log = mocker.patch("external_resources.api.log")

    with pytest.raises(HTTPError):
        make_wayback_request(WAYBACK_API_URL, {}, WAYBACK_HEADERS)
    mock_log.exception.assert_called_once()


def test_submit_url_to_wayback(mocker):
    """submit_url_to_wayback should ask the Wayback Machine to save the url"""
    mock_request = mocker.patch(
        "external_resources.api.make_wayback_request",
        return_value={"job_id": "job_1"},
    )

    assert submit_url_to_wayback("http://google.com") == {"job_id": "job_1"}
    mock_request.assert_called_once_with(
        WAYBACK_API_URL,
        {"url": "http://google.com", "skip_first_archive": "1"},
        WAYBACK_HEADERS,
    )


def test_check_wayback_jobs_status_batch(mocker):
    """check_wayback_jobs_status_batch should request all job ids at once"""
    results = [{"job_id": "job_1"}, {"job_id": "job_2"}]
    mock_request = mocker.patch(
        "external_resources.api.make_wayback_request", return_value=results
    )

    assert check_wayback_jobs_status_batch(["job_1", "job_2"]) == results
    mock_request.assert_called_once_with(
        WAYBACK_CHECK_STATUS_URL, {"job_ids": "job_1,job_2"}, WAYBACK_HEADERS
    )


def test_check_wayback_jobs_status_batch_no_jobs(mocker):
    """No request should be made when there are no job ids"""
    mock_request = mocker.patch("external_resources.api.make_wayback_request")

    assert check_wayback_jobs_status_batch([]) == []
    mock_request.assert_not_called()
