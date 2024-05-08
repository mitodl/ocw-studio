"""Content sync utility functionality tests"""
import os

import pytest
from botocore.exceptions import ClientError
from moto import mock_s3

from content_sync.constants import (
    DEV_END,
    DEV_ENDPOINT_URL,
    DEV_START,
    NON_DEV_END,
    NON_DEV_START,
    TARGET_OFFLINE,
    TARGET_ONLINE,
    VERSION_DRAFT,
    VERSION_LIVE,
)
from content_sync.test_constants import (
    EVEN_TAGS_TEST_FILE,
    EXPECTED_REMAINING_STRING_DEV,
    EXPECTED_REMAINING_STRING_NON_DEV,
    HUGO_ARG_TEST_OVERRIDES,
    TEST_DEFAULT_HUGO_ARGS,
    UNEVEN_TAGS_TEST_FILE,
)
from content_sync.utils import (
    check_matching_tags,
    get_cli_endpoint_url,
    get_common_pipeline_vars,
    get_destination_filepath,
    get_destination_url,
    get_hugo_arg_string,
    get_ocw_studio_api_url,
    get_publishable_sites,
    get_site_content_branch,
    move_s3_object,
    strip_lines_between,
)
from main.s3_utils import get_boto3_client
from ocw_import.conftest import MOCK_BUCKET_NAME, setup_s3
from websites.factories import WebsiteContentFactory, WebsiteStarterFactory
from websites.site_config_api import ConfigItem, SiteConfig

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("has_missing_name", "is_bad_config_item"),
    [
        [True, False],  # noqa: PT007
        [False, True],  # noqa: PT007
    ],
)
def test_get_destination_filepath_errors(mocker, has_missing_name, is_bad_config_item):
    """
    get_destination_filepath should log an error and return None if the site config is missing the given name, or if
    the config item does not have a properly configured destination.
    """
    patched_log = mocker.patch("content_sync.utils.log")
    # From basic-site-config.yml
    config_item_name = "blog"
    if is_bad_config_item:
        mocker.patch.object(
            SiteConfig,
            "find_item_by_name",
            return_value=ConfigItem(
                item={"name": config_item_name, "poorly": "configured"}
            ),
        )
    starter = WebsiteStarterFactory.build()
    content = WebsiteContentFactory.build(
        is_page_content=False,
        type="non-existent-config-name" if has_missing_name else config_item_name,
    )
    return_value = get_destination_filepath(
        content=content, site_config=SiteConfig(starter.config)
    )
    patched_log.error.assert_called_once()
    assert return_value is None


def test_get_destination_url_errors(mocker):
    """
    get_destination_url should log an error if it is called with a a WebsiteContent object without
    is_page_content set to true
    """
    patched_log = mocker.patch("content_sync.utils.log")
    # From basic-site-config.yml
    config_item_name = "blog"
    starter = WebsiteStarterFactory.build()
    content = WebsiteContentFactory.build(
        is_page_content=False,
        type=config_item_name,
    )
    return_value = get_destination_url(
        content=content, site_config=SiteConfig(starter.config)
    )
    patched_log.error.assert_called_once()
    assert return_value is None


@pytest.mark.parametrize(
    ("is_page_content", "dirpath", "filename", "expected"),
    [
        [True, "content/pages", "_index", "/pages/"],  # noqa: PT007
        [True, "content/pages", "hx_network", "/pages/hx_network"],  # noqa: PT007
        [  # noqa: PT007
            True,
            "content/pages/lecture-notes",
            "java_3d_lecture",
            "/pages/lecture-notes/java_3d_lecture",
        ],
        [True, "content/resources", "image", "/resources/image"],  # noqa: PT007
        [False, "", "", None],  # noqa: PT007
    ],
)
def test_get_destination_url(is_page_content, dirpath, filename, expected):
    """get_destination_url should create a url for a piece of content"""
    content = WebsiteContentFactory.create(
        is_page_content=is_page_content, dirpath=dirpath, filename=filename
    )
    assert (
        get_destination_url(content, SiteConfig(content.website.starter.config))
        == expected
    )


@pytest.mark.parametrize(
    ("is_page_content", "dirpath", "filename", "expected"),
    [
        [True, "content/pages", "_index", "content/pages/_index.md"],  # noqa: PT007
        [  # noqa: PT007
            True,
            "content/pages",
            "hx_network",
            "content/pages/hx_network.md",
        ],
        [  # noqa: PT007
            True,
            "content/pages/lecture-notes",
            "java_3d_lecture",
            "content/pages/lecture-notes/java_3d_lecture.md",
        ],
        [  # noqa: PT007
            True,
            "content/resources",
            "image",
            "content/resources/image.md",
        ],
        [False, "", "", None],  # noqa: PT007
        [False, "config/_default/menus.yaml", "menus.yaml", None],  # noqa: PT007
    ],
)
def test_get_destination_filepath(is_page_content, dirpath, filename, expected):
    """get_destination_filepath should create the filepath for a piece of content"""
    content = WebsiteContentFactory.create(
        is_page_content=is_page_content, dirpath=dirpath, filename=filename
    )
    assert (
        get_destination_filepath(content, SiteConfig(content.website.starter.config))
        == expected
    )


@mock_s3
def test_move_s3_object(settings):
    """S3 key for a moved object should be changed as expected"""
    settings.AWS_STORAGE_BUCKET_NAME = MOCK_BUCKET_NAME
    setup_s3(settings)
    client = get_boto3_client("s3")
    from_path = "biology/config/_default/menus.yaml"
    to_path = "courses/mycourse/_default/menus.yaml"
    assert client.get_object(Bucket=MOCK_BUCKET_NAME, Key=from_path) is not None
    with pytest.raises(ClientError):
        client.get_object(Bucket=MOCK_BUCKET_NAME, Key=to_path)
    move_s3_object(from_path, to_path)
    with pytest.raises(ClientError):
        client.get_object(Bucket=MOCK_BUCKET_NAME, Key=from_path)
    assert client.get_object(Bucket=MOCK_BUCKET_NAME, Key=to_path) is not None


@pytest.mark.parametrize("is_dev", [True, False])
def test_get_common_pipeline_vars(settings, mocker, is_dev):
    """get_common_pipeline_vars should return the correct values based on environment"""
    if is_dev:
        settings.ENVIRONMENT = "dev"
        settings.OCW_STUDIO_DRAFT_URL = "http://localhost:8044"
        settings.OCW_STUDIO_LIVE_URL = "http://localhost:8045"
        settings.STATIC_API_BASE_URL_DRAFT = "http://draft.ocw.mit.edu"
        settings.STATIC_API_BASE_URL_LIVE = "http://ocw.mit.edu"
        settings.STATIC_API_BASE_URL_TEST = "http://test.ocw.mit.edu"
    else:
        settings.ENVIRONMENT = "not_dev"
    pipeline_vars = get_common_pipeline_vars()
    assert pipeline_vars["preview_bucket_name"] == settings.AWS_PREVIEW_BUCKET_NAME
    assert pipeline_vars["publish_bucket_name"] == settings.AWS_PUBLISH_BUCKET_NAME
    assert (
        pipeline_vars["offline_preview_bucket_name"]
        == settings.AWS_OFFLINE_PREVIEW_BUCKET_NAME
    )
    assert (
        pipeline_vars["offline_publish_bucket_name"]
        == settings.AWS_OFFLINE_PUBLISH_BUCKET_NAME
    )
    assert pipeline_vars["storage_bucket_name"] == settings.AWS_STORAGE_BUCKET_NAME
    assert pipeline_vars["artifacts_bucket_name"] == settings.AWS_ARTIFACTS_BUCKET_NAME
    if is_dev:
        assert (
            pipeline_vars["static_api_base_url_draft"]
            == settings.STATIC_API_BASE_URL_DRAFT
        )
        assert (
            pipeline_vars["static_api_base_url_live"]
            == settings.STATIC_API_BASE_URL_LIVE
        )
        assert (
            pipeline_vars["static_api_base_url_test"]
            == settings.STATIC_API_BASE_URL_TEST
        )
        assert (
            pipeline_vars["resource_base_url_draft"] == settings.RESOURCE_BASE_URL_DRAFT
        )
        assert (
            pipeline_vars["resource_base_url_live"] == settings.RESOURCE_BASE_URL_LIVE
        )
    else:
        assert (
            pipeline_vars["static_api_base_url_draft"] == settings.OCW_STUDIO_DRAFT_URL
        )
        assert pipeline_vars["static_api_base_url_live"] == settings.OCW_STUDIO_LIVE_URL
        assert pipeline_vars["resource_base_url_draft"] == ""
        assert pipeline_vars["resource_base_url_live"] == ""


@pytest.mark.parametrize("is_dev", [True, False])
def test_get_cli_endpoint_url(settings, mocker, is_dev):
    """get_cli_endpoint_url should return the correct value based on environment"""
    mock_is_dev = mocker.patch("content_sync.utils.is_dev")
    mock_is_dev.return_value = is_dev
    cli_endpoint_url = get_cli_endpoint_url()
    expected_cli_endpoint_url = f" --endpoint-url {DEV_ENDPOINT_URL}" if is_dev else ""
    assert cli_endpoint_url == expected_cli_endpoint_url


@pytest.mark.parametrize("is_dev", [True, False])
def test_get_ocw_studio_api_url(settings, mocker, is_dev):
    """get_cli_endpoint_url should return the correct value based on environment"""
    mock_is_dev = mocker.patch("content_sync.utils.is_dev")
    mock_is_dev.return_value = is_dev
    ocw_studio_api_url = get_ocw_studio_api_url()
    expected_ocw_studio_api_url = (
        "http://10.1.0.102:8043" if is_dev else settings.SITE_BASE_URL
    )
    assert ocw_studio_api_url == expected_ocw_studio_api_url


@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
def test_get_publishable_sites(settings, mocker, mass_build_websites, version):
    """get_publishable_sites should return a queryset of sites that have been published before"""
    unpublished_site = mass_build_websites[0]
    if version == VERSION_DRAFT:
        unpublished_site.draft_publish_date = None
    else:
        unpublished_site.publish_date = None
    unpublished_site.save()
    for index, test_site_slug in enumerate(settings.OCW_TEST_SITE_SLUGS):
        test_site = mass_build_websites[index + 1]
        test_site.name = test_site_slug
        test_site.save()
    assert len(mass_build_websites) == 7
    publishable_sites = get_publishable_sites(version)
    assert publishable_sites.count() == 4


@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
def test_get_site_content_branch(settings, mocker, mass_build_websites, version):
    """get_publishable_sites should return the proper git branch based on version"""
    site_content_branch = get_site_content_branch(version)
    if version == VERSION_DRAFT:
        assert site_content_branch == settings.GIT_BRANCH_PREVIEW
    else:
        assert site_content_branch == settings.GIT_BRANCH_RELEASE


@pytest.mark.parametrize("build_target", [TARGET_OFFLINE, TARGET_ONLINE])
@pytest.mark.parametrize("pipeline_name", [VERSION_DRAFT, VERSION_LIVE])
@pytest.mark.parametrize("default_args", [TEST_DEFAULT_HUGO_ARGS])
@pytest.mark.parametrize("override_args", HUGO_ARG_TEST_OVERRIDES)
def test_get_hugo_arg_string(build_target, pipeline_name, default_args, override_args):
    """get_hugo_arg_string should return a string that can be passed to the hugo executable with the appropriate overrides if specified"""
    override_string = override_args["input"]
    expected_overrides = override_args["output"]
    arg_string = get_hugo_arg_string(
        build_target, pipeline_name, default_args, override_string
    )
    for key in default_args:
        value = default_args[key]
        expected_string = f"{key} {value}" if value != "" else key
        if key not in expected_overrides:
            assert expected_string in arg_string
        else:
            assert expected_string not in arg_string
    for key in expected_overrides:
        value = expected_overrides[key]
        expected_string = f"{key} {value}" if value != "" else key
        assert expected_string in arg_string


def test_check_matching_tags():
    """check_matching_tags should throw an exception if the tags don't match"""
    uneven_tags_test_file = os.path.join(  # noqa: PTH118
        os.path.dirname(__file__), UNEVEN_TAGS_TEST_FILE  # noqa: PTH120
    )
    even_tags_test_file = os.path.join(  # noqa: PTH118
        os.path.dirname(__file__), EVEN_TAGS_TEST_FILE  # noqa: PTH120
    )  # noqa: PTH118, PTH120, RUF100
    with open(  # noqa: PTH123
        uneven_tags_test_file, encoding="utf-8"
    ) as test_config_file:  # noqa: PTH123, RUF100
        test_config = test_config_file.read()
        with pytest.raises(ValueError):  # noqa: PT011
            check_matching_tags(test_config, DEV_START, DEV_END)
        assert check_matching_tags(test_config, NON_DEV_START, NON_DEV_END) is True
    with open(  # noqa: PTH123
        even_tags_test_file, encoding="utf-8"
    ) as test_config_file:  # noqa: PTH123, RUF100
        test_config = test_config_file.read()
        assert check_matching_tags(test_config, DEV_START, DEV_END) is True
        assert check_matching_tags(test_config, NON_DEV_START, NON_DEV_END) is True


@pytest.mark.parametrize(
    ("start_tag", "end_tag", "expected"),
    [
        [DEV_START, DEV_END, EXPECTED_REMAINING_STRING_DEV],  # noqa: PT007
        [NON_DEV_START, NON_DEV_END, EXPECTED_REMAINING_STRING_NON_DEV],  # noqa: PT007
    ],
)
def test_strip_lines_between(start_tag, end_tag, expected):
    """Check that strip_lines_between strips the expected content"""
    even_tags_test_file = os.path.join(  # noqa: PTH118
        os.path.dirname(__file__), EVEN_TAGS_TEST_FILE  # noqa: PTH120
    )  # noqa: PTH118, PTH120, RUF100
    with open(  # noqa: PTH123
        even_tags_test_file, encoding="utf-8"
    ) as test_config_file:  # noqa: PTH123, RUF100
        test_config = test_config_file.read()
        assert expected == strip_lines_between(test_config, start_tag, end_tag)


@pytest.mark.parametrize(
    ("start_tag", "end_tag"),
    [
        ["# DEV START", "# DEV END"],  # noqa: PT007
        ["# STARTT DEV", "# END DEV"],  # noqa: PT007
        ["# START DEV", "# ENDD DEV"],  # noqa: PT007
        ["#START DEV", "# END DEV"],  # noqa: PT007
        ["# START DEV", "#END DEV"],  # noqa: PT007
        ["# START PROD", "# END DEV"],  # noqa: PT007
        ["# START DEV", "# END PROD"],  # noqa: PT007
    ],
)
def test_bad_tags(start_tag, end_tag):
    """Make sure errors are thrown if a bad combination of start_tag and end_tag are passed"""
    even_tags_test_file = os.path.join(  # noqa: PTH118
        os.path.dirname(__file__), EVEN_TAGS_TEST_FILE  # noqa: PTH120
    )  # noqa: PTH118, PTH120, RUF100
    with open(  # noqa: PTH123
        even_tags_test_file, encoding="utf-8"
    ) as test_config_file:  # noqa: PTH123, RUF100
        test_config = test_config_file.read()
        with pytest.raises(ValueError):  # noqa: PT011
            check_matching_tags(test_config, start_tag, end_tag)
