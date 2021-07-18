""" concourse tests """
import json

import pytest
from django.core.exceptions import ImproperlyConfigured
from requests import HTTPError

from content_sync.pipelines.concourse import ConcourseApi, ConcourseGithubPipeline
from websites.factories import WebsiteFactory, WebsiteStarterFactory


pytestmark = pytest.mark.django_db
# pylint:disable=redefined-outer-name


@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("iterator", [True, False])
def test_api_get_with_headers(mocker, stream, iterator):
    """ ConcourseApi.get_with_headers function should work as expected """
    mock_text = '[{"test": "output"}]' if iterator else '{"test": "output"}'
    stream_output = ["yielded"]
    mocker.patch(
        "content_sync.pipelines.concourse.BaseConcourseApi.iter_sse_stream",
        return_value=stream_output,
    )
    mocker.patch("content_sync.pipelines.concourse.BaseConcourseApi.auth")
    mock_response = mocker.Mock(
        text=mock_text, status_code=200, headers={"X-Test": "header"}
    )
    mock_get = mocker.patch(
        "content_sync.pipelines.concourse.requests.get", return_value=mock_response
    )
    url_path = "/api/v1/teams/myteam/pipelines/draft/config?vars={site=mypipeline}"
    api = ConcourseApi("http://test.edu", "test", "test", "myteam")
    result, headers = api.get_with_headers(url_path, stream=stream, iterator=iterator)
    mock_get.assert_called_once_with(
        f"http://test.edu{url_path}", headers=mocker.ANY, stream=stream
    )
    assert headers == mock_response.headers
    assert result == (stream_output if stream else json.loads(mock_response.text))


@pytest.mark.parametrize("headers", [None, {"X-Concourse-Config-Version": 101}])
@pytest.mark.parametrize("status_code", [200, 401])
@pytest.mark.parametrize("ok_response", [True, False])
def test_api_put(mocker, headers, status_code, ok_response):
    """ ConcourseApi.put_with_headers function should work as expected """
    mock_auth = mocker.patch("content_sync.pipelines.concourse.BaseConcourseApi.auth")
    mock_response = mocker.Mock(
        status_code=status_code, headers={"X-Test": "header_value"}
    )
    mocker.patch(
        "content_sync.pipelines.concourse.BaseConcourseApi._is_response_ok",
        return_value=ok_response,
    )
    mock_put = mocker.patch(
        "content_sync.pipelines.concourse.requests.put", return_value=mock_response
    )
    url_path = "/api/v1/teams/myteam/pipelines/draft/config?vars={site=mypipeline}"
    api = ConcourseApi("http://test.edu", "test", "test", "myteam")
    data = {"test": "value"}
    assert api.put_with_headers(url_path, data=data, headers=headers) is (
        status_code == 200
    )
    mock_put.assert_any_call(
        f"http://test.edu{url_path}", data=data, headers=mocker.ANY
    )
    if headers is not None:
        _, kwargs = mock_put.call_args_list[-1]
        key, value = list(headers.items())[0]
        assert kwargs["headers"][key] == value
        assert kwargs["data"] == data
    assert mock_auth.call_count == 1 if ok_response else 2


def test_upsert_website_pipeline_missing_settings(settings):
    """An exception should be raised if required settings are missing"""
    settings.AWS_PREVIEW_BUCKET_NAME = None
    website = WebsiteFactory.create()
    with pytest.raises(ImproperlyConfigured):
        ConcourseGithubPipeline(website)


@pytest.mark.parametrize("version", ["live", "draft"])
@pytest.mark.parametrize("home_page", [True, False])
@pytest.mark.parametrize("pipeline_exists", [True, False])
def test_upsert_website_pipelines(
    mocker, settings, version, home_page, pipeline_exists
):  # pylint:disable=too-many-locals
    """The correct concourse API args should be made for a website"""
    settings.ROOT_WEBSITE_NAME = "ocw-www-course"
    starter = WebsiteStarterFactory.create()
    if home_page:
        name = settings.ROOT_WEBSITE_NAME
        starter.config["root-url-path"] = ""
    else:
        name = "standard-course"
        starter = WebsiteStarterFactory.create()
        starter.config["root-url-path"] = "courses"
    website = WebsiteFactory.create(starter=starter, name=name)

    instance_vars = "{" + f"%22site%22%3A%20%22{website.name}%22" + "}"
    url_path = f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{version}/config?vars={instance_vars}"
    mocker.patch("content_sync.pipelines.concourse.BaseConcourseApi.auth")
    if not pipeline_exists:
        mock_get = mocker.patch(
            "content_sync.pipelines.concourse.ConcourseApi.get_with_headers",
            side_effect=HTTPError(),
        )
    else:
        mock_get = mocker.patch(
            "content_sync.pipelines.concourse.ConcourseApi.get_with_headers",
            return_value=({}, {"X-Concourse-Config-Version": "3"}),
        )
    mock_put = mocker.patch("content_sync.pipelines.concourse.ConcourseApi.put")
    mock_put_headers = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi.put_with_headers"
    )
    pipeline = ConcourseGithubPipeline(website)
    pipeline.upsert_website_pipeline()

    mock_get.assert_any_call(url_path)
    mock_put_headers.assert_any_call(
        url_path,
        data=mocker.ANY,
        headers=({"X-Concourse-Config-Version": "3"} if pipeline_exists else None),
    )
    _, kwargs = mock_put_headers.call_args_list[0]

    config_str = json.dumps(kwargs)

    if home_page:
        assert (
            f"s3 sync s3://{settings.AWS_STORAGE_BUCKET_NAME}/{website.name} s3://{settings.AWS_PREVIEW_BUCKET_NAME}/{website.name}"
            in config_str
        )

        assert (
            f"aws s3 sync course-markdown/public s3://{settings.AWS_PREVIEW_BUCKET_NAME}/\\\\n"
            in config_str
        )

        assert "purge_all" in config_str
    else:
        assert (
            f"s3 sync s3://{settings.AWS_STORAGE_BUCKET_NAME}/courses/{website.name} s3://{settings.AWS_PREVIEW_BUCKET_NAME}/courses/{website.name}"
            in config_str
        )

        assert (
            f"aws s3 sync course-markdown/public s3://{settings.AWS_PREVIEW_BUCKET_NAME}/courses/{website.name}\\\\n"
            in config_str
        )

        assert f"purge/courses/{website.name}" in config_str
    mock_put.assert_any_call(url_path.replace("config", "unpause"))
