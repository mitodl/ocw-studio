""" concourse tests """
import json
from html import unescape
from urllib.parse import quote, urljoin

import pytest
from django.core.exceptions import ImproperlyConfigured
from requests import HTTPError

from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from content_sync.pipelines.base import (
    BaseMassBuildSitesPipeline,
    BaseUnpublishedSiteRemovalPipeline,
)
from content_sync.pipelines.concourse import (
    ConcourseApi,
    MassBuildSitesPipeline,
    SitePipeline,
    ThemeAssetsPipeline,
    UnpublishedSiteRemovalPipeline, GeneralPipeline,
)
from websites.constants import STARTER_SOURCE_GITHUB, STARTER_SOURCE_LOCAL
from websites.factories import WebsiteFactory, WebsiteStarterFactory


pytestmark = pytest.mark.django_db
# pylint:disable=redefined-outer-name,unused-argument

AUTH_URLS = [
    '"/sky/issuer/auth/local?req=xtvhpv2hdsvjgownxnpowsiph&amp;foo=bar"',
    '"/sky/issuer/auth/local?access_type=offline&client_id=concourse-web&amp;redirect_uri=https%3A%2F%2Fcicd-ci.odl.mit.edu%2Fsky%2Fcallback"',
    '"/sky/issuer/auth/local/login?back=%2Fsky%2Fissuer%2Fauth%3Faccess_type%3Doffline%26client_id%3Dconcourse-web%26redirect_uri&amp;foo=bar%"',
]


PIPELINES_LIST = [
    {'id': 1,
     'name': VERSION_DRAFT,
     'instance_vars': {'site': 'test-site-1'},
     'paused': False,
     'public': False,
     'archived': False,
     'team_name': 'team1',
     'last_updated': 1652878975},
    {'id': 2,
     'name': VERSION_DRAFT,
     'instance_vars': {'site': 'test-site-2'},
     'paused': False,
     'public': False,
     'archived': False,
     'team_name': 'team1',
     'last_updated': 1652878976},
    {'id': 3,
     'name': VERSION_LIVE,
     'instance_vars': {'site': 'test-site-1'},
     'paused': False,
     'public': False,
     'archived': False,
     'team_name': 'team1',
     'last_updated': 1652878975},
    {'id': 4,
     'name': VERSION_LIVE,
     'instance_vars': {'site': 'test-site-2'},
     'paused': False,
     'public': False,
     'archived': False,
     'team_name': 'team1',
     'last_updated': 1652878976},
    {'id': 5,
     'name': "something_else",
     'instance_vars': {'site': 'test-site-other1'},
     'paused': False,
     'public': False,
     'archived': False,
     'team_name': 'team1',
     'last_updated': 1652878976},
]


@pytest.fixture
def mock_auth(mocker):
    """Mock the concourse api auth method"""
    mocker.patch("content_sync.pipelines.concourse.ConcourseApi.auth")


@pytest.fixture
def pipeline_settings(settings):
    """ Default settings for pipelines"""
    settings.ROOT_WEBSITE_NAME = "ocw-www-course"
    settings.OCW_STUDIO_DRAFT_URL = "https://draft.ocw.mit.edu"
    settings.OCW_STUDIO_LIVE_URL = "https://live.ocw.mit.edu"
    settings.OCW_IMPORT_STARTER_SLUG = "custom_slug"


@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("iterator", [True, False])
def test_api_get_with_headers(mocker, mock_auth, stream, iterator):
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
def test_api_put(mocker, mock_auth, headers, status_code, ok_response):
    """ ConcourseApi.put_with_headers function should work as expected """
    mock_auth = mocker.patch("content_sync.pipelines.concourse.ConcourseApi.auth")
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
    settings,
    mocker,
    mock_auth,
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
        site_path = None
    else:
        name = "standard-course"
        starter.config["root-url-path"] = "courses"
        site_path = "courses/my-site-fall-2020"

    website = WebsiteFactory.create(starter=starter, name=name, url_path=site_path)

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
            f"s3 sync s3://{settings.AWS_STORAGE_BUCKET_NAME}/courses/{website.name} s3://{bucket}/{website.url_path}"
            in config_str
        )
        assert (
            f"aws s3 sync course-markdown/public s3://{bucket}/{website.url_path}"
            in config_str
        )
    assert f"purge/{website.name}" in config_str
    assert f" --metadata site-id={website.name}" in config_str
    has_soft_purge_header = "Fastly-Soft-Purge" in config_str
    assert has_soft_purge_header is not hard_purge


@pytest.mark.parametrize("is_private_repo", [True, False])
def test_upsert_pipeline_public_vs_private(
    settings, mocker, mock_auth, is_private_repo
):
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
def test_upsert_website_pipelines_invalid_starter(mocker, mock_auth, source, path):
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
def test_trigger_pipeline_build(settings, mocker, mock_auth, version):
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
@pytest.mark.parametrize("action", ["pause", "unpause"])
def test_pause_unpause_pipeline(settings, mocker, mock_auth, version, action):
    """pause_pipeline and unpause_pipeline should make the expected put requests"""
    settings.CONCOURSE_TEAM = "myteam"
    mock_put = mocker.patch("content_sync.pipelines.concourse.ConcourseApi.put")
    website = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB, path="https://github.com/org/repo/config"
        )
    )
    pipeline = SitePipeline(website)
    getattr(pipeline, f"{action}_pipeline")(version)
    mock_put.assert_any_call(
        f"/api/v1/teams/myteam/pipelines/{version}/{action}{pipeline.instance_vars}"
    )
    pipeline = ThemeAssetsPipeline()
    getattr(pipeline, f"{action}_pipeline")(ThemeAssetsPipeline.PIPELINE_NAME)
    mock_put.assert_any_call(
        f"/api/v1/teams/myteam/pipelines/ocw-theme-assets/{action}{pipeline.instance_vars}"
    )


@pytest.mark.parametrize("names", [None, [VERSION_DRAFT, VERSION_LIVE]])
def test_list_pipelines(settings, mocker, mock_auth, names):
    """The correct list of pipelines should be returned"""
    settings.CONCOURSE_TEAM = "team1"
    mocker.patch("content_sync.pipelines.concourse.ConcourseApi.list_pipelines", return_value=PIPELINES_LIST)
    pipeline = GeneralPipeline()
    matching_list = pipeline.list_pipelines(names=names)
    assert len(matching_list) == (5 if not names else 4)
    assert matching_list == (PIPELINES_LIST if not names else PIPELINES_LIST[0:4])


@pytest.mark.parametrize("names", [None, [VERSION_DRAFT, VERSION_LIVE]])
def test_delete_pipelines(settings, mocker, mock_auth, names):
    """The correct list of pipelines should be deleted"""
    settings.CONCOURSE_TEAM = "team1"
    mocker.patch("content_sync.pipelines.concourse.ConcourseApi.list_pipelines", return_value=PIPELINES_LIST)
    mock_api_delete = mocker.patch("content_sync.pipelines.concourse.ConcourseApi.delete")
    pipeline = GeneralPipeline()
    pipeline.delete_pipelines(names=names)
    for idx, site_pipeline in enumerate(PIPELINES_LIST):
        if idx < 4 or names is None:
            pipe_name = PIPELINES_LIST[idx]['name']
            pipe_vars = f'?vars={quote(json.dumps(PIPELINES_LIST[idx]["instance_vars"]))}'
            mock_api_delete.assert_any_call(f"/api/v1/teams/team1/pipelines/{pipe_name}{pipe_vars}")


def test_get_build_status(mocker, mock_auth):
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
def test_upsert_pipeline(settings, mocker, mock_auth, pipeline_exists):
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
        f"s3://ol-eng-artifacts/ocw-hugo-themes/{settings.GITHUB_WEBHOOK_BRANCH}"
        in config_str
    )


@pytest.mark.parametrize("pipeline_exists", [True, False])
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
def test_upsert_mass_build_pipeline(
    settings, pipeline_settings, mocker, mock_auth, pipeline_exists, version
):  # pylint:disable=too-many-locals,too-many-arguments
    """The mass build pipeline should have expected configuration"""
    hugo_projects_path = "https://github.com/org/repo"
    WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB, path=f"{hugo_projects_path}/site"
        ),
        name=settings.ROOT_WEBSITE_NAME,
    )
    instance_vars = f'?vars={quote(json.dumps({"version": version}))}'
    url_path = f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{BaseMassBuildSitesPipeline.PIPELINE_NAME}/config{instance_vars}"

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
    pipeline = MassBuildSitesPipeline(version)
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
    assert (
        f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/$S3_PATH s3://{bucket}/$SITE_URL"
        in config_str
    )
    assert bucket in config_str
    assert version in config_str
    assert f"{hugo_projects_path}.git" in config_str
    assert api_url in config_str


@pytest.mark.parametrize("pipeline_exists", [True, False])
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
def test_unpublished_site_removal_pipeline(
    settings, pipeline_settings, mocker, mock_auth, pipeline_exists, version
):  # pylint:disable=too-many-locals,too-many-arguments
    """The unpublished sites removal pipeline should have expected configuration"""
    url_path = f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{BaseUnpublishedSiteRemovalPipeline.PIPELINE_NAME}/config"

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
    pipeline = UnpublishedSiteRemovalPipeline()
    pipeline.upsert_pipeline()

    mock_get.assert_any_call(url_path)
    mock_put_headers.assert_any_call(
        url_path,
        data=mocker.ANY,
        headers=({"X-Concourse-Config-Version": "3"} if pipeline_exists else None),
    )
    _, kwargs = mock_put_headers.call_args_list[0]
    config_str = json.dumps(kwargs)
    assert settings.SITE_BASE_URL in config_str
    assert settings.AWS_PUBLISH_BUCKET_NAME in config_str
    assert VERSION_LIVE in config_str


@pytest.mark.parametrize(
    "get_urls, post_url",
    [
        [[AUTH_URLS[0], AUTH_URLS[0]], AUTH_URLS[0]],
        [AUTH_URLS[0:2], AUTH_URLS[1]],
        [AUTH_URLS[1:], AUTH_URLS[2]],
    ],
)
@pytest.mark.parametrize("auth_token", ["123abc", None])
@pytest.mark.parametrize("password", [None, "password"])
@pytest.mark.parametrize("get_status", [200, 500])
@pytest.mark.parametrize("post_status", [200, 500])
def test_api_auth(
    mocker,
    settings,
    get_urls,
    post_url,
    auth_token,
    password,
    get_status,
    post_status,
):  # pylint:disable=too-many-arguments
    """verify that the auth function posts to the expected url and returns the expected response"""
    settings.CONCOURSE_PASSWORD = password
    mock_skymarshal = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi._get_skymarshal_auth",
        return_value=auth_token,
    )
    mock_session = mocker.patch(
        "content_sync.pipelines.concourse.ConcourseApi._set_new_session"
    )
    mock_session.return_value.get.side_effect = [
        mocker.Mock(text=url, status_code=get_status) for url in [*get_urls, *get_urls]
    ]
    mock_session.return_value.post.return_value = mocker.Mock(
        text="ok", status_code=post_status
    )
    api = ConcourseApi(
        settings.CONCOURSE_URL,
        settings.CONCOURSE_USERNAME,
        settings.CONCOURSE_PASSWORD,
        settings.CONCOURSE_TEAM,
    )
    get_count = 2 if get_status == 200 else 1
    assert mock_session.return_value.get.call_count == (get_count if password else 0)
    if password and get_count == 2:
        mock_session.return_value.post.assert_called_once_with(
            unescape(urljoin(settings.CONCOURSE_URL, post_url.replace('"', ""))),
            data={"login": "test", "password": password},
        )
    else:
        mock_session.return_value.post.assert_not_called()
    assert mock_skymarshal.call_count == (
        1 if password and get_status == 200 and post_status == 200 else 0
    )
    api.ATC_AUTH = None
    assert api.auth() is (
        auth_token is not None
        and password is not None
        and get_status == 200
        and post_status == 200
    )
