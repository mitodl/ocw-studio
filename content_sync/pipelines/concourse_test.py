""" concourse tests """
import json
from urllib.parse import quote

import pytest
from django.core.exceptions import ImproperlyConfigured
from requests import HTTPError

from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.pipelines.base import BaseMassPublishPipeline
from content_sync.pipelines.concourse import (
    ConcourseApi,
    MassPublishPipeline,
    SitePipeline,
    ThemeAssetsPipeline,
)
from websites.constants import STARTER_SOURCE_GITHUB, STARTER_SOURCE_LOCAL
from websites.factories import WebsiteFactory, WebsiteStarterFactory


pytestmark = pytest.mark.django_db
# pylint:disable=redefined-outer-name


@pytest.fixture(autouse=True)
def mock_concoursepy_auth(mocker):
    """Mock the concourse api auth method"""
    mocker.patch("content_sync.pipelines.concourse.BaseConcourseApi.auth")


@pytest.fixture
def pipeline_settings(settings):
    """ Default settings for pipelines"""
    settings.ROOT_WEBSITE_NAME = "ocw-www-course"
    settings.OCW_STUDIO_DRAFT_URL = "https://draft.ocw.mit.edu"
    settings.OCW_STUDIO_LIVE_URL = "https://live.ocw.mit.edu"
    settings.OCW_IMPORT_STARTER_SLUG = "custom_slug"


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
        SitePipeline(website)


@pytest.mark.parametrize("version", [VERSION_LIVE, VERSION_DRAFT])
@pytest.mark.parametrize("home_page", [True, False])
@pytest.mark.parametrize("pipeline_exists", [True, False])
@pytest.mark.parametrize("hard_purge", [True, False])
@pytest.mark.parametrize("with_api", [True, False])
def test_upsert_website_pipelines(
    mocker,
    settings,
    pipeline_settings,
    version,
    home_page,
    pipeline_exists,
    hard_purge,
    with_api,
):  # pylint:disable=too-many-locals,too-many-arguments,too-many-branches,unused-argument
    """The correct concourse API args should be made for a website"""
    settings.CONCOURSE_HARD_PURGE = hard_purge

    hugo_projects_path = "https://github.com/org/repo"
    starter = WebsiteStarterFactory.create(
        source=STARTER_SOURCE_GITHUB, path=f"{hugo_projects_path}/site"
    )
    if home_page:
        name = settings.ROOT_WEBSITE_NAME
        starter.config["root-url-path"] = ""
    else:
        name = "standard-course"
        starter.config["root-url-path"] = "courses"
    website = WebsiteFactory.create(starter=starter, name=name)

    instance_vars = f"%7B%22site%22%3A%20%22{website.name}%22%7D"
    url_path = f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{version}/config?vars={instance_vars}"

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
    mock_put_headers = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi.put_with_headers"
    )
    existing_api = ConcourseApi("a", "b", "c", "d") if with_api else None
    pipeline = SitePipeline(website, api=existing_api)
    assert (pipeline.api == existing_api) is with_api
    pipeline.upsert_pipeline()

    mock_get.assert_any_call(url_path)
    mock_put_headers.assert_any_call(
        url_path,
        data=mocker.ANY,
        headers=({"X-Concourse-Config-Version": "3"} if pipeline_exists else None),
    )
    if version == VERSION_DRAFT:
        _, kwargs = mock_put_headers.call_args_list[0]
        bucket = settings.AWS_PREVIEW_BUCKET_NAME
        api_url = settings.OCW_STUDIO_DRAFT_URL
    else:
        _, kwargs = mock_put_headers.call_args_list[1]
        bucket = settings.AWS_PUBLISH_BUCKET_NAME
        api_url = settings.OCW_STUDIO_LIVE_URL

    config_str = json.dumps(kwargs)

    assert f"{hugo_projects_path}.git" in config_str
    assert settings.OCW_GTM_ACCOUNT_ID in config_str
    assert settings.OCW_IMPORT_STARTER_SLUG in config_str
    assert api_url in config_str
    if home_page:
        assert (
            f"s3 sync s3://{settings.AWS_STORAGE_BUCKET_NAME}/{website.name} s3://{bucket}/{website.name}"
            in config_str
        )
        assert f"aws s3 sync course-markdown/public s3://{bucket}/" in config_str
    else:
        assert (
            f"s3 sync s3://{settings.AWS_STORAGE_BUCKET_NAME}/courses/{website.name} s3://{bucket}/courses/{website.name}"
            in config_str
        )
        assert (
            f"aws s3 sync course-markdown/public s3://{bucket}/courses/{website.name}"
            in config_str
        )
    assert f"purge/{website.name}" in config_str
    assert f" --metadata site-id={website.name}" in config_str
    has_soft_purge_header = "Fastly-Soft-Purge" in config_str
    assert has_soft_purge_header is not hard_purge


@pytest.mark.parametrize("is_private_repo", [True, False])
def test_upsert_pipeline_public_vs_private(settings, mocker, is_private_repo):
    """Pipeline config shoould have expected course-markdown git url and private git key setting if applicable"""
    settings.CONCOURSE_IS_PRIVATE_REPO = is_private_repo
    settings.GIT_DOMAIN = "github.test.edu"
    settings.GIT_ORGANIZATION = "testorg"
    settings.OCW_STUDIO_DRAFT_URL = "https://draft.test.edu"
    settings.OCW_STUDIO_LIVE_URL = "https://live.test.edu"
    mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi.get_with_headers",
        return_value=(None, {"X-Concourse-Config-Version": 1}),
    )
    mock_put_headers = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi.put_with_headers"
    )
    starter = WebsiteStarterFactory.create(
        source=STARTER_SOURCE_GITHUB, path="https://github.com/org/repo/site"
    )
    website = WebsiteFactory.create(starter=starter)
    private_key_str = "((git-private-key))"
    if is_private_repo:
        repo_url_str = f"git@{settings.GIT_DOMAIN}:{settings.GIT_ORGANIZATION}/{website.short_id}.git"
    else:
        repo_url_str = f"https://{settings.GIT_DOMAIN}/{settings.GIT_ORGANIZATION}/{website.short_id}.git"
    pipeline = SitePipeline(website)
    pipeline.upsert_pipeline()
    _, kwargs = mock_put_headers.call_args_list[0]
    config_str = json.dumps(kwargs)
    assert repo_url_str in config_str
    assert (private_key_str in config_str) is is_private_repo


@pytest.mark.parametrize(
    "source,path",
    [
        [STARTER_SOURCE_GITHUB, "badvalue"],
        [STARTER_SOURCE_LOCAL, "https://github.com/testorg/testrepo/ocw-course"],
    ],
)
def test_upsert_website_pipelines_invalid_starter(mocker, source, path):
    """A pipeline should not be upserted for invalid WebsiteStarters"""
    mock_get = mocker.patch("content_sync.pipelines.concourse.ConcourseApi.get")
    mock_put = mocker.patch("content_sync.pipelines.concourse.ConcourseApi.put")
    mock_put_headers = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi.put_with_headers"
    )
    starter = WebsiteStarterFactory.create(source=source, path=path)
    website = WebsiteFactory.create(starter=starter)
    pipeline = SitePipeline(website)
    pipeline.upsert_pipeline()
    mock_get.assert_not_called()
    mock_put.assert_not_called()
    mock_put_headers.assert_not_called()


@pytest.mark.parametrize("version", ["live", "draft"])
def test_trigger_pipeline_build(settings, mocker, version):
    """The correct requests should be made to trigger a pipeline build"""
    job_name = "build-ocw-site"
    mock_get = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi.get",
        return_value={"config": {"jobs": [{"name": job_name}]}},
    )
    expected_build_id = 123456
    mock_post = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi.post",
        return_value={"id": expected_build_id},
    )
    website = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB, path="https://github.com/org/repo/config"
        )
    )
    team = settings.CONCOURSE_TEAM
    pipeline = SitePipeline(website)
    build_id = pipeline.trigger_pipeline_build(version)
    assert build_id == expected_build_id
    mock_get.assert_called_once_with(
        f"/api/v1/teams/{team}/pipelines/{version}/config{pipeline.instance_vars}"
    )
    mock_post.assert_called_once_with(
        f"/api/v1/teams/{team}/pipelines/{version}/jobs/{job_name}/builds{pipeline.instance_vars}"
    )
    job_name = "build-theme-assets"
    mock_get = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi.get",
        return_value={"config": {"jobs": [{"name": job_name}]}},
    )
    pipeline = ThemeAssetsPipeline()
    build_id = pipeline.trigger_pipeline_build(ThemeAssetsPipeline.PIPELINE_NAME)
    mock_get.assert_any_call(
        f"/api/v1/teams/{team}/pipelines/ocw-theme-assets/config{pipeline.instance_vars}"
    )
    mock_post.assert_any_call(
        f"/api/v1/teams/{team}/pipelines/ocw-theme-assets/jobs/{job_name}/builds{pipeline.instance_vars}"
    )
    assert build_id == expected_build_id


@pytest.mark.parametrize("version", ["live", "draft"])
def test_unpause_pipeline(settings, mocker, version):
    """unpause_pipeline should make the expected put request"""
    settings.CONCOURSE_TEAM = "myteam"
    mock_put = mocker.patch("content_sync.pipelines.concourse.ConcourseApi.put")
    website = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB, path="https://github.com/org/repo/config"
        )
    )
    pipeline = SitePipeline(website)
    pipeline.unpause_pipeline(version)
    mock_put.assert_any_call(
        f"/api/v1/teams/myteam/pipelines/{version}/unpause{pipeline.instance_vars}"
    )
    pipeline = ThemeAssetsPipeline()
    pipeline.unpause_pipeline(ThemeAssetsPipeline.PIPELINE_NAME)
    mock_put.assert_any_call(
        f"/api/v1/teams/myteam/pipelines/ocw-theme-assets/unpause{pipeline.instance_vars}"
    )


def test_get_build_status(mocker):
    """Get the status of the build for the site"""
    build_id = 123456
    status = "status"
    mock_get = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi.get_build",
        return_value={"status": status},
    )
    website = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB, path="https://github.com/org/repo/config"
        )
    )
    pipeline = SitePipeline(website)
    assert pipeline.get_build_status(build_id) == status
    mock_get.assert_called_once_with(build_id)


@pytest.mark.parametrize("pipeline_exists", [True, False])
def test_upsert_pipeline(mocker, settings, pipeline_exists):
    """ Test upserting the theme assets pipeline """
    instance_vars = f"%7B%22branch%22%3A%20%22{settings.GITHUB_WEBHOOK_BRANCH}%22%7D"
    url_path = f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/ocw-theme-assets/config?vars={instance_vars}"

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
    mock_put_headers = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi.put_with_headers"
    )
    api = ConcourseApi("http://test.edu", "test", "test", "myteam")
    pipeline = ThemeAssetsPipeline(api)
    pipeline.upsert_pipeline()
    mock_get.assert_any_call(url_path)
    mock_put_headers.assert_any_call(
        url_path,
        data=mocker.ANY,
        headers=({"X-Concourse-Config-Version": "3"} if pipeline_exists else None),
    )
    _, kwargs = mock_put_headers.call_args_list[0]
    config_str = json.dumps(kwargs)
    assert settings.SEARCH_API_URL in config_str
    assert settings.AWS_PREVIEW_BUCKET_NAME in config_str
    assert settings.AWS_PUBLISH_BUCKET_NAME in config_str
    assert (
        f"s3-remote:ol-eng-artifacts/ocw-hugo-themes/{settings.GITHUB_WEBHOOK_BRANCH}"
        in config_str
    )


@pytest.mark.parametrize("pipeline_exists", [True, False])
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
def test_upsert_mass_publish_pipeline(
    settings, pipeline_settings, mocker, pipeline_exists, version
):  # pylint:disable=too-many-locals,unused-argument
    """The mass publish pipeline should have expected configuration"""
    hugo_projects_path = "https://github.com/org/repo"
    WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB, path=f"{hugo_projects_path}/site"
        ),
        name=settings.ROOT_WEBSITE_NAME,
    )
    instance_vars = f'?vars={quote(json.dumps({"version": version}))}'
    url_path = f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{BaseMassPublishPipeline.PIPELINE_NAME}/config{instance_vars}"

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
    mock_put_headers = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi.put_with_headers"
    )
    pipeline = MassPublishPipeline(version)
    pipeline.upsert_pipeline()

    mock_get.assert_any_call(url_path)
    mock_put_headers.assert_any_call(
        url_path,
        data=mocker.ANY,
        headers=({"X-Concourse-Config-Version": "3"} if pipeline_exists else None),
    )
    _, kwargs = mock_put_headers.call_args_list[0]
    if version == VERSION_DRAFT:
        bucket = settings.AWS_PREVIEW_BUCKET_NAME
        api_url = settings.OCW_STUDIO_DRAFT_URL
    else:
        bucket = settings.AWS_PUBLISH_BUCKET_NAME
        api_url = settings.OCW_STUDIO_LIVE_URL
    config_str = json.dumps(kwargs)
    assert settings.OCW_GTM_ACCOUNT_ID in config_str
    assert bucket in config_str
    assert version in config_str
    assert f"{hugo_projects_path}.git" in config_str
    assert api_url in config_str
