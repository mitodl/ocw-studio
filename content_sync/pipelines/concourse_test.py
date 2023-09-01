"""concourse tests"""
import json
from html import unescape
from urllib.parse import quote, urljoin

import pytest
from django.core.exceptions import ImproperlyConfigured
from requests import HTTPError

from content_sync.constants import (
    TARGET_OFFLINE,
    TARGET_ONLINE,
    VERSION_DRAFT,
    VERSION_LIVE,
)
from content_sync.pipelines.base import (
    BaseMassBuildSitesPipeline,
    BaseUnpublishedSiteRemovalPipeline,
)
from content_sync.pipelines.concourse import (
    MassBuildSitesPipeline,
    PipelineApi,
    SitePipeline,
    ThemeAssetsPipeline,
    UnpublishedSiteRemovalPipeline,
)
from content_sync.pipelines.definitions.concourse.common.identifiers import (
    OCW_HUGO_PROJECTS_GIT_IDENTIFIER,
    OCW_HUGO_THEMES_GIT_IDENTIFIER,
)
from content_sync.utils import get_hugo_arg_string, get_common_pipeline_vars, get_theme_branch
from main.constants import PRODUCTION_NAMES
from main.utils import is_dev
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
    {
        "id": 1,
        "name": VERSION_DRAFT,
        "instance_vars": {"site": "test-site-1"},
        "paused": False,
        "public": False,
        "archived": False,
        "team_name": "team1",
        "last_updated": 1652878975,
    },
    {
        "id": 2,
        "name": VERSION_DRAFT,
        "instance_vars": {"site": "test-site-2"},
        "paused": False,
        "public": False,
        "archived": False,
        "team_name": "team1",
        "last_updated": 1652878976,
    },
    {
        "id": 3,
        "name": VERSION_LIVE,
        "instance_vars": {"site": "test-site-1"},
        "paused": False,
        "public": False,
        "archived": False,
        "team_name": "team1",
        "last_updated": 1652878975,
    },
    {
        "id": 4,
        "name": VERSION_LIVE,
        "instance_vars": {"site": "test-site-2"},
        "paused": False,
        "public": False,
        "archived": False,
        "team_name": "team1",
        "last_updated": 1652878976,
    },
    {
        "id": 5,
        "name": "something_else",
        "instance_vars": {"site": "test-site-other1"},
        "paused": False,
        "public": False,
        "archived": False,
        "team_name": "team1",
        "last_updated": 1652878976,
    },
]


@pytest.fixture()
def mock_auth(mocker):  # noqa: PT004
    """Mock the concourse api auth method"""
    mocker.patch("content_sync.pipelines.concourse.PipelineApi.auth")


@pytest.fixture(params=["test", "dev"])
def pipeline_settings(settings, request):  # noqa: PT004
    """Default settings for pipelines"""  # noqa: D401
    env = request.param
    settings.ENVIRONMENT = env
    settings.AWS_STORAGE_BUCKET_NAME = "storage_bucket_test"
    settings.AWS_PREVIEW_BUCKET_NAME = "draft_bucket_test"
    settings.AWS_PUBLISH_BUCKET_NAME = "live_bucket_test"
    settings.AWS_OFFLINE_PREVIEW_BUCKET_NAME = "draft_offline_bucket_test"
    settings.AWS_OFFLINE_PUBLISH_BUCKET_NAME = "live_offline_bucket_test"
    settings.GITHUB_WEBHOOK_BRANCH = "main"
    settings.GIT_BRANCH_PREVIEW = "preview"
    settings.GIT_BRANCH_RELEASE = "release"
    settings.ROOT_WEBSITE_NAME = "ocw-www-course"
    settings.OCW_HUGO_THEMES_BRANCH = "main"
    settings.OCW_HUGO_PROJECTS_BRANCH = "main"
    settings.OCW_STUDIO_DRAFT_URL = "https://draft.ocw.mit.edu"
    settings.OCW_STUDIO_LIVE_URL = "https://live.ocw.mit.edu"
    settings.OCW_IMPORT_STARTER_SLUG = "custom_slug"
    settings.OCW_COURSE_STARTER_SLUG = "another_custom_slug"
    settings.OCW_NEXT_SEARCH_WEBHOOK_KEY = "abc123"
    settings.OPEN_DISCUSSIONS_URL = "https://open.mit.edu"
    if env == "dev":
        settings.AWS_ACCESS_KEY_ID = "minio_root_user"
        settings.AWS_SECRET_ACCESS_KEY = "minio_root_password"  # noqa: S105
        settings.AWS_STORAGE_BUCKET_NAME = "storage_bucket_dev"
        settings.AWS_PREVIEW_BUCKET_NAME = "draft_bucket_dev"
        settings.AWS_PUBLISH_BUCKET_NAME = "live_bucket_dev"
        settings.AWS_OFFLINE_PREVIEW_BUCKET_NAME = "draft_offline_bucket_dev"
        settings.AWS_OFFLINE_PUBLISH_BUCKET_NAME = "live_offline_bucket_dev"
        settings.AWS_ARTIFACTS_BUCKET_NAME = "artifact_buckets_dev"
        settings.OCW_HUGO_THEMES_BRANCH = "themes_dev"
        settings.OCW_HUGO_PROJECTS_BRANCH = "projects_dev"
        settings.RESOURCE_BASE_URL_DRAFT = "https://draft.ocw.mit.edu"
        settings.RESOURCE_BASE_URL_LIVE = "https://live.ocw.mit.edu"


@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("iterator", [True, False])
def test_api_get_with_headers(mocker, mock_auth, stream, iterator):
    """PipelineApi.get_with_headers function should work as expected"""
    mock_text = '[{"test": "output"}]' if iterator else '{"test": "output"}'
    stream_output = ["yielded"]
    mocker.patch(
        "content_sync.pipelines.concourse.Api.iter_sse_stream",
        return_value=stream_output,
    )
    mock_response = mocker.Mock(
        text=mock_text, status_code=200, headers={"X-Test": "header"}
    )
    mock_get = mocker.patch(
        "content_sync.pipelines.concourse.requests.get", return_value=mock_response
    )
    url_path = "/api/v1/teams/myteam/pipelines/draft/config?vars={site=mypipeline}"
    api = PipelineApi("http://test.edu", "test", "test", "myteam")
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
    """PipelineApi.put_with_headers function should work as expected"""
    mock_auth = mocker.patch("content_sync.pipelines.concourse.PipelineApi.auth")
    mock_response = mocker.Mock(
        status_code=status_code, headers={"X-Test": "header_value"}
    )
    mocker.patch(
        "content_sync.pipelines.concourse.Api._is_response_ok",
        return_value=ok_response,
    )
    mock_put = mocker.patch(
        "content_sync.pipelines.concourse.requests.put", return_value=mock_response
    )
    url_path = "/api/v1/teams/myteam/pipelines/draft/config?vars={site=mypipeline}"
    api = PipelineApi("http://test.edu", "test", "test", "myteam")
    data = {"test": "value"}
    assert api.put_with_headers(url_path, data=data, headers=headers) is (
        status_code == 200
    )
    mock_put.assert_any_call(
        f"http://test.edu{url_path}", data=data, headers=mocker.ANY
    )
    if headers is not None:
        _, kwargs = mock_put.call_args_list[-1]
        key, value = next(iter(headers.items()))
        assert kwargs["headers"][key] == value
        assert kwargs["data"] == data
    assert mock_auth.call_count == 1 if ok_response else 2


@pytest.mark.parametrize("status_code", [200, 403])
@pytest.mark.parametrize("ok_response", [True, False])
def test_api_delete(mocker, mock_auth, status_code, ok_response):
    """PipelineApi.delete function should work as expected"""
    mock_auth = mocker.patch("content_sync.pipelines.concourse.PipelineApi.auth")
    mock_response = mocker.Mock(
        status_code=status_code, headers={"X-Test": "header_value"}
    )
    mocker.patch(
        "content_sync.pipelines.concourse.Api._is_response_ok",
        return_value=ok_response,
    )
    mock_delete = mocker.patch(
        "content_sync.pipelines.concourse.requests.delete", return_value=mock_response
    )
    url_path = "/api/v1/teams/myteam/pipelines/draft?vars={site=mypipeline}"
    api = PipelineApi("http://test.edu", "test", "test", "myteam")
    data = {"test": "value"}
    assert api.delete(url_path, data=data) is (status_code == 200)
    mock_delete.assert_any_call(
        f"http://test.edu{url_path}", data=data, headers=mocker.ANY
    )
    assert mock_auth.call_count == 1 if ok_response else 2


@pytest.mark.parametrize("names", [None, [VERSION_DRAFT, VERSION_LIVE]])
def test_get_pipelines(settings, mocker, mock_auth, names):
    """The correct list of pipelines should be returned"""
    settings.CONCOURSE_TEAM = "team1"
    mocker.patch(
        "content_sync.pipelines.concourse.Api.list_pipelines",
        return_value=PIPELINES_LIST,
    )
    api = PipelineApi()
    matching_list = api.get_pipelines(names=names)
    assert len(matching_list) == (5 if not names else 4)
    assert matching_list == (PIPELINES_LIST if not names else PIPELINES_LIST[0:4])


@pytest.mark.parametrize("names", [None, [VERSION_DRAFT, VERSION_LIVE]])
def test_delete_pipelines(settings, mocker, mock_auth, names):
    """The correct list of pipelines should be deleted"""
    settings.CONCOURSE_TEAM = "team1"
    mocker.patch(
        "content_sync.pipelines.concourse.Api.list_pipelines",
        return_value=PIPELINES_LIST,
    )
    mock_api_delete = mocker.patch(
        "content_sync.pipelines.concourse.PipelineApi.delete"
    )
    api = PipelineApi()
    api.delete_pipelines(names=names)
    for idx, site_pipeline in enumerate(PIPELINES_LIST):
        if idx < 4 or names is None:
            pipe_name = site_pipeline["name"]
            pipe_vars = f'?vars={quote(json.dumps(site_pipeline["instance_vars"]))}'
            mock_api_delete.assert_any_call(
                f"/api/v1/teams/team1/pipelines/{pipe_name}{pipe_vars}"
            )


def test_upsert_website_pipeline_missing_settings(settings):
    """An exception should be raised if required settings are missing"""
    settings.ENVIRONMENT = "test"
    settings.AWS_PREVIEW_BUCKET_NAME = None
    website = WebsiteFactory.create()
    with pytest.raises(ImproperlyConfigured):
        SitePipeline(website)


@pytest.mark.parametrize("env_name", ["production", "rc"])
@pytest.mark.parametrize("version", [VERSION_LIVE, VERSION_DRAFT])
@pytest.mark.parametrize("home_page", [True, False])
@pytest.mark.parametrize("pipeline_exists", [True, False])
@pytest.mark.parametrize("hard_purge", [True, False])
@pytest.mark.parametrize("with_api", [True, False])
def test_upsert_website_pipelines(  # noqa: PLR0913, PLR0915
    settings,
    pipeline_settings,
    mocker,
    mock_auth,
    version,
    home_page,
    pipeline_exists,
    hard_purge,
    with_api,
    env_name,
):  # pylint:disable=too-many-locals,too-many-arguments,too-many-statements
    """The correct concourse API args should be made for a website"""
    # Set AWS expectations based on environment
    env = settings.ENVIRONMENT
    expected_template_vars = get_common_pipeline_vars()
    expected_endpoint_prefix = (
        "--endpoint-url http://10.1.0.100:9000 " if env == "dev" else ""
    )
    settings.ENV_NAME = env_name
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
            "content_sync.pipelines.concourse.PipelineApi.get_with_headers",
            side_effect=HTTPError(),
        )
    else:
        mock_get = mocker.patch(
            "content_sync.pipelines.concourse.PipelineApi.get_with_headers",
            return_value=({}, {"X-Concourse-Config-Version": "3"}),
        )
    mock_put_headers = mocker.patch(
        "content_sync.pipelines.concourse.PipelineApi.put_with_headers"
    )
    existing_api = PipelineApi("a", "b", "c", "d") if with_api else None
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
        expected_site_content_branch = settings.GIT_BRANCH_PREVIEW
        expected_web_bucket = expected_template_vars["preview_bucket_name"]
        expected_offline_bucket = expected_template_vars["offline_preview_bucket_name"]
        expected_resource_base_url = expected_template_vars["resource_base_url_draft"]
        expected_ocw_studio_url = settings.OCW_STUDIO_DRAFT_URL
        expected_static_api_url = (
            settings.STATIC_API_BASE_URL or settings.OCW_STUDIO_DRAFT_URL
            if is_dev()
            else settings.OCW_STUDIO_DRAFT_URL
        )
    else:
        _, kwargs = mock_put_headers.call_args_list[1]
        expected_site_content_branch = settings.GIT_BRANCH_RELEASE
        expected_web_bucket = expected_template_vars["publish_bucket_name"]
        expected_offline_bucket = expected_template_vars["offline_publish_bucket_name"]
        expected_resource_base_url = expected_template_vars["resource_base_url_live"]
        expected_ocw_studio_url = settings.OCW_STUDIO_LIVE_URL
        expected_static_api_url = (
            settings.STATIC_API_BASE_URL or settings.OCW_STUDIO_LIVE_URL
            if is_dev()
            else settings.OCW_STUDIO_LIVE_URL
        )

    expected_is_root_website = 1 if home_page else 0
    expected_base_url = "" if home_page else website.get_url_path()
    expected_static_resources_subdirectory = (
        f"/{website.get_url_path()}/" if home_page else "/"
    )
    expected_delete_flag = "" if home_page else " --delete"
    if (
        expected_site_content_branch == settings.GIT_BRANCH_PREVIEW
        or settings.ENV_NAME not in PRODUCTION_NAMES
    ):
        expected_noindex = "true"
    else:
        expected_noindex = "false"
    expected_instance_vars = f'?vars={quote(json.dumps({"site": website.name}))}'
    starter_slug = starter.slug
    base_hugo_args = {"--themesDir": f"../{OCW_HUGO_THEMES_GIT_IDENTIFIER}/"}
    base_online_args = base_hugo_args.copy()
    base_online_args.update(
        {
            "--config": f"../{OCW_HUGO_PROJECTS_GIT_IDENTIFIER}/{starter_slug}/config.yaml",
            "--baseURL": f"/{expected_base_url}",
            "--destination": "output-online",
        }
    )
    base_offline_args = base_hugo_args.copy()
    base_offline_args.update(
        {
            "--config": f"../{OCW_HUGO_PROJECTS_GIT_IDENTIFIER}/{starter_slug}/config-offline.yaml",
            "--baseURL": "/",
            "--destination": "output-offline",
        }
    )
    expected_hugo_args_online = get_hugo_arg_string(
        TARGET_ONLINE,
        version,
        base_online_args,
        "",
    )
    expected_hugo_args_offline = get_hugo_arg_string(
        TARGET_OFFLINE,
        version,
        base_offline_args,
        "",
    )

    config_str = json.dumps(kwargs)

    assert f"{hugo_projects_path}.git" in config_str
    assert settings.OCW_GTM_ACCOUNT_ID in config_str
    assert settings.OCW_IMPORT_STARTER_SLUG in config_str
    assert settings.OCW_COURSE_STARTER_SLUG in config_str
    assert expected_ocw_studio_url in config_str
    assert f"aws s3 {expected_endpoint_prefix}sync" in config_str
    assert f'\\"is_root_website\\": {expected_is_root_website}' in config_str
    assert f'\\"short_id\\": \\"{website.short_id}\\"' in config_str
    assert f'\\"site_name\\": \\"{website.name}\\"' in config_str
    assert f'\\"s3_path\\": \\"{website.s3_path}\\"' in config_str
    assert f'\\"url_path\\": \\"{website.get_url_path()}\\"' in config_str
    assert f'\\"base_url\\": \\"{expected_base_url}\\"' in config_str
    assert (
        f'\\"static_resources_subdirectory\\": \\"{expected_static_resources_subdirectory}\\"'
        in config_str
    )
    assert f'\\"delete_flag\\": \\"{expected_delete_flag}\\"' in config_str
    assert f'\\"noindex\\": \\"{expected_noindex}\\"' in config_str
    assert f'\\"pipeline_name\\": \\"{version}\\"' in config_str
    assert f'\\"instance_vars\\": \\"{expected_instance_vars}\\"' in config_str
    assert f'\\"static_api_url\\": \\"{expected_static_api_url}\\"' in config_str
    assert (
        f'\\"storage_bucket\\": \\"{expected_template_vars["storage_bucket_name"]}\\"'
        in config_str
    )
    assert (
        f'\\"artifacts_bucket\\": \\"{expected_template_vars["artifacts_bucket_name"]}\\"'
        in config_str
    )
    assert f'\\"web_bucket\\": \\"{expected_web_bucket}\\"' in config_str
    assert f'\\"offline_bucket\\": \\"{expected_offline_bucket}\\"' in config_str
    assert f'\\"resource_base_url\\": \\"{expected_resource_base_url}\\"' in config_str
    assert f'\\"ocw_studio_url\\": \\"{expected_ocw_studio_url}\\"' in config_str
    assert (
        f'\\"site_content_branch\\": \\"{expected_site_content_branch}\\"' in config_str
    )
    assert (
        f'\\"ocw_hugo_themes_branch\\": \\"{settings.OCW_HUGO_THEMES_BRANCH}\\"'
        in config_str
    )
    assert (
        f'\\"ocw_hugo_projects_url\\": \\"{starter.ocw_hugo_projects_url}\\"'
        in config_str
    )
    assert (
        f'\\"ocw_hugo_projects_branch\\": \\"{settings.OCW_HUGO_PROJECTS_BRANCH}\\"'
        in config_str
    )
    assert f'\\"hugo_args_online\\": \\"{expected_hugo_args_online}\\"' in config_str
    assert f'\\"hugo_args_offline\\": \\"{expected_hugo_args_offline}\\"' in config_str


@pytest.mark.parametrize(
    ("source", "path"),
    [
        [STARTER_SOURCE_GITHUB, "badvalue"],  # noqa: PT007
        [  # noqa: PT007
            STARTER_SOURCE_LOCAL,
            "https://github.com/testorg/testrepo/ocw-course",
        ],
    ],
)
def test_upsert_website_pipelines_invalid_starter(mocker, mock_auth, source, path):
    """A pipeline should not be upserted for invalid WebsiteStarters"""
    mock_get = mocker.patch("content_sync.pipelines.concourse.PipelineApi.get")
    mock_put = mocker.patch("content_sync.pipelines.concourse.PipelineApi.put")
    mock_put_headers = mocker.patch(
        "content_sync.pipelines.concourse.PipelineApi.put_with_headers"
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
    job_name = "build-online-ocw-site"
    mock_get = mocker.patch(
        "content_sync.pipelines.concourse.PipelineApi.get",
        return_value={"config": {"jobs": [{"name": job_name}]}},
    )
    expected_build_id = 123456
    mock_post = mocker.patch(
        "content_sync.pipelines.concourse.PipelineApi.post",
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
        "content_sync.pipelines.concourse.PipelineApi.get",
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
    mock_put = mocker.patch("content_sync.pipelines.concourse.PipelineApi.put")
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


def test_get_build_status(mocker, mock_auth):
    """Get the status of the build for the site"""
    build_id = 123456
    status = "status"
    mock_get = mocker.patch(
        "content_sync.pipelines.concourse.PipelineApi.get_build",
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
def test_upsert_pipeline(
    settings, pipeline_settings, mocker, mock_auth, pipeline_exists
):  # pylint:disable=too-many-locals
    """Test upserting the theme assets pipeline"""
    instance_vars = f"%7B%22branch%22%3A%20%22{get_theme_branch()}%22%7D"
    url_path = f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/ocw-theme-assets/config?vars={instance_vars}"

    if not pipeline_exists:
        mock_get = mocker.patch(
            "content_sync.pipelines.concourse.PipelineApi.get_with_headers",
            side_effect=HTTPError(),
        )
    else:
        mock_get = mocker.patch(
            "content_sync.pipelines.concourse.PipelineApi.get_with_headers",
            return_value=({}, {"X-Concourse-Config-Version": "3"}),
        )
    mock_put_headers = mocker.patch(
        "content_sync.pipelines.concourse.PipelineApi.put_with_headers"
    )
    api = PipelineApi("http://test.edu", "test", "test", "myteam")
    pipeline = ThemeAssetsPipeline(api=api)
    pipeline.upsert_pipeline()
    mock_get.assert_any_call(url_path)
    mock_put_headers.assert_any_call(
        url_path,
        data=mocker.ANY,
        headers=({"X-Concourse-Config-Version": "3"} if pipeline_exists else None),
    )
    _, kwargs = mock_put_headers.call_args_list[0]
    config_str = json.dumps(kwargs)
    expected_template_vars = get_common_pipeline_vars()
    expected_branch = get_theme_branch()
    preview_bucket_name = expected_template_vars["preview_bucket_name"]
    publish_bucket_name = expected_template_vars["publish_bucket_name"]
    artifacts_bucket_name = expected_template_vars["artifacts_bucket_name"]
    assert settings.SEARCH_API_URL in config_str
    assert preview_bucket_name in config_str
    assert publish_bucket_name in config_str
    assert (
        f"s3://{artifacts_bucket_name}/ocw-hugo-themes/{expected_branch}" in config_str
    )


@pytest.mark.parametrize("pipeline_exists", [True, False])
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
@pytest.mark.parametrize("themes_branch", ["", "main", "test_themes_branch"])
@pytest.mark.parametrize("projects_branch", ["", "main", "test_projects_branch"])
@pytest.mark.parametrize("prefix", ["", "/test_prefix", "test_prefix"])
@pytest.mark.parametrize("starter", ["", "ocw-course"])
@pytest.mark.parametrize("offline", [True, False])
def test_upsert_mass_build_pipeline(  # noqa: C901, PLR0912, PLR0913, PLR0915
    settings,
    pipeline_settings,
    mocker,
    mock_auth,
    pipeline_exists,
    version,
    themes_branch,
    projects_branch,
    prefix,
    starter,
    offline,
):  # pylint:disable=too-many-locals,too-many-arguments,too-many-statements,too-many-branches
    """The mass build pipeline should have expected configuration"""
    expected_template_vars = get_common_pipeline_vars()
    hugo_projects_path = "https://github.com/org/repo"
    WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(
            source=STARTER_SOURCE_GITHUB, path=f"{hugo_projects_path}/site"
        ),
        name=settings.ROOT_WEBSITE_NAME,
    )
    themes_branch = (
        themes_branch if themes_branch and not is_dev() else get_theme_branch()
    )
    projects_branch = (
        projects_branch
        if projects_branch and not is_dev()
        else settings.OCW_HUGO_THEMES_BRANCH or settings.GITHUB_WEBHOOK_BRANCH
    )
    if prefix:
        stripped_prefix = prefix[1:] if prefix.startswith("/") else prefix
    else:
        stripped_prefix = ""
    build_drafts = " --buildDrafts" if version == VERSION_DRAFT else ""
    endpoint_url = (
        " --endpoint-url http://10.1.0.100:9000"
        if settings.ENVIRONMENT == "dev"
        else ""
    )
    instance_vars = {
        "version": version,
        "themes_branch": themes_branch,
        "projects_branch": projects_branch,
        "prefix": stripped_prefix,
        "starter": starter,
        "offline": offline,
    }
    instance_vars_str = f"?vars={quote(json.dumps(instance_vars))}"
    url_path = f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{BaseMassBuildSitesPipeline.PIPELINE_NAME}/config{instance_vars_str}"

    if not pipeline_exists:
        mock_get = mocker.patch(
            "content_sync.pipelines.concourse.PipelineApi.get_with_headers",
            side_effect=HTTPError(),
        )
    else:
        mock_get = mocker.patch(
            "content_sync.pipelines.concourse.PipelineApi.get_with_headers",
            return_value=({}, {"X-Concourse-Config-Version": "3"}),
        )
    mock_put_headers = mocker.patch(
        "content_sync.pipelines.concourse.PipelineApi.put_with_headers"
    )
    pipeline = MassBuildSitesPipeline(**instance_vars)
    pipeline.upsert_pipeline()

    mock_get.assert_any_call(url_path)
    mock_put_headers.assert_any_call(
        url_path,
        data=mocker.ANY,
        headers=({"X-Concourse-Config-Version": "3"} if pipeline_exists else None),
    )
    _, kwargs = mock_put_headers.call_args_list[0]
    if version == VERSION_DRAFT:
        bucket = expected_template_vars["preview_bucket_name"]
        offline_bucket = expected_template_vars["offline_preview_bucket_name"]
        static_api_url = settings.OCW_STUDIO_DRAFT_URL
    elif version == VERSION_LIVE:
        bucket = expected_template_vars["publish_bucket_name"]
        offline_bucket = expected_template_vars["offline_publish_bucket_name"]
        static_api_url = settings.OCW_STUDIO_LIVE_URL
    config_str = json.dumps(kwargs)
    assert settings.OCW_GTM_ACCOUNT_ID in config_str
    assert bucket in config_str
    assert version in config_str
    if starter:
        assert f"&starter={starter}" in config_str
    if stripped_prefix:
        assert f'\\"PREFIX\\": \\"{stripped_prefix}\\"' in config_str
    assert f'\\"branch\\": \\"{themes_branch}\\"' in config_str
    assert f'\\"branch\\": \\"{projects_branch}\\"' in config_str
    assert f"{hugo_projects_path}.git" in config_str
    assert static_api_url in config_str
    if (
        version == VERSION_DRAFT in config_str
        or settings.ENV_NAME not in PRODUCTION_NAMES
    ):
        expected_noindex = '\\"NOINDEX\\": true'
    else:
        expected_noindex = '\\"NOINDEX\\": false'
    assert expected_noindex in config_str
    if offline:
        assert "PULLING IN STATIC RESOURCES FOR $NAME" in config_str
        assert "touch ./content/static_resources/_index.md" in config_str
        assert f"HUGO_RESULT=$(hugo --themesDir ../ocw-hugo-themes/ --quiet --baseURL / --config ../ocw-hugo-projects/$STARTER_SLUG/config.yaml{build_drafts}) || HUGO_RESULT=1"  # noqa: PLW0129
        assert (
            f"PUBLISH_S3_RESULT=$(aws s3{endpoint_url} sync ./ s3://{offline_bucket}$PREFIX/$BASE_URL --metadata site-id=$NAME --only-show-errors $DELETE) || PUBLISH_S3_RESULT=1"
            in config_str
        )
        assert (
            f"PUBLISH_S3_RESULT=$(aws s3{endpoint_url} sync ./ s3://{bucket}$PREFIX/$BASE_URL"
            in config_str
        )
        assert "$SHORT_ID.zip" in config_str
        if settings.ENVIRONMENT == "dev":
            assert (
                f"STUDIO_S3_RESULT=$(aws s3{endpoint_url} sync s3://{settings.AWS_STORAGE_BUCKET_NAME}/$S3_PATH ./content/static_resources --exclude *.mp4 --only-show-errors) || STUDIO_S3_RESULT=1"
                in config_str
            )
    else:
        assert (
            "cp ../webpack-json/webpack.json ../ocw-hugo-themes/base-theme/data"
            in config_str
        )
        assert (
            f"HUGO_RESULT=$(hugo --themesDir ../ocw-hugo-themes/ --quiet --baseURL $PREFIX/$BASE_URL --config ../ocw-hugo-projects/$STARTER_SLUG/config.yaml{build_drafts}) || HUGO_RESULT=1"
            in config_str
        )
        assert (
            f"STUDIO_S3_RESULT=$(aws s3{endpoint_url} sync s3://{settings.AWS_STORAGE_BUCKET_NAME}/$S3_PATH s3://{bucket}$PREFIX/$SITE_URL --metadata site-id=$NAME --only-show-errors) || STUDIO_S3_RESULT=1"
            in config_str
        )
        assert (
            f"PUBLISH_S3_RESULT=$(aws s3{endpoint_url} sync $SHORT_ID/public s3://{bucket}$PREFIX/$BASE_URL --metadata site-id=$NAME --only-show-errors) || PUBLISH_S3_RESULT=1"
            in config_str
        )
        if settings.ENVIRONMENT != "dev":
            assert settings.OCW_NEXT_SEARCH_WEBHOOK_KEY in config_str
            assert (
                f"{settings.OPEN_DISCUSSIONS_URL}/api/v0/ocw_next_webhook/"
                in config_str
            )


@pytest.mark.parametrize("pipeline_exists", [True, False])
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
def test_unpublished_site_removal_pipeline(  # noqa: PLR0913
    settings, pipeline_settings, mocker, mock_auth, pipeline_exists, version
):  # pylint:disable=too-many-locals,too-many-arguments
    """The unpublished sites removal pipeline should have expected configuration"""
    template_vars = get_common_pipeline_vars()
    url_path = f"/api/v1/teams/{settings.CONCOURSE_TEAM}/pipelines/{BaseUnpublishedSiteRemovalPipeline.PIPELINE_NAME}/config"

    if not pipeline_exists:
        mock_get = mocker.patch(
            "content_sync.pipelines.concourse.PipelineApi.get_with_headers",
            side_effect=HTTPError(),
        )
    else:
        mock_get = mocker.patch(
            "content_sync.pipelines.concourse.PipelineApi.get_with_headers",
            return_value=({}, {"X-Concourse-Config-Version": "3"}),
        )
    mock_put_headers = mocker.patch(
        "content_sync.pipelines.concourse.PipelineApi.put_with_headers"
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
    assert template_vars["ocw_studio_url"] in config_str
    assert template_vars["publish_bucket_name"] in config_str
    assert VERSION_LIVE in config_str


@pytest.mark.parametrize(
    ("get_urls", "post_url"),
    [
        [[AUTH_URLS[0], AUTH_URLS[0]], AUTH_URLS[0]],  # noqa: PT007
        [AUTH_URLS[0:2], AUTH_URLS[1]],  # noqa: PT007
        [AUTH_URLS[1:], AUTH_URLS[2]],  # noqa: PT007
    ],
)
@pytest.mark.parametrize("auth_token", ["123abc", None])
@pytest.mark.parametrize("password", [None, "password"])
@pytest.mark.parametrize("get_status", [200, 500])
@pytest.mark.parametrize("post_status", [200, 500])
def test_api_auth(  # noqa: PLR0913
    mocker,
    settings,
    get_urls,
    post_url,
    auth_token,
    password,
    get_status,
    post_status,
):  # pylint:disable=too-many-arguments
    """Verify that the auth function posts to the expected url and returns the expected response"""
    settings.CONCOURSE_PASSWORD = password
    mock_skymarshal = mocker.patch(
        "content_sync.pipelines.concourse.PipelineApi._get_skymarshal_auth",
        return_value=auth_token,
    )
    mock_session = mocker.patch(
        "content_sync.pipelines.concourse.PipelineApi._set_new_session"
    )
    mock_session.return_value.get.side_effect = [
        mocker.Mock(text=url, status_code=get_status) for url in [*get_urls, *get_urls]
    ]
    mock_session.return_value.post.return_value = mocker.Mock(
        text="ok", status_code=post_status
    )
    api = PipelineApi(
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
