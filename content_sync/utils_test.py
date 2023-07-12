"""Content sync utility functionality tests"""
import os

import pytest
from botocore.exceptions import ClientError
from moto import mock_s3

from content_sync.constants import (
    DEV_END,
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
    get_destination_filepath,
    get_destination_url,
    get_hugo_arg_string,
    move_s3_object,
    strip_lines_between,
)
from main.s3_utils import get_boto3_client
from ocw_import.conftest import MOCK_BUCKET_NAME, setup_s3
from websites.factories import WebsiteContentFactory, WebsiteStarterFactory
from websites.site_config_api import ConfigItem, SiteConfig


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "has_missing_name, is_bad_config_item",
    [
        [True, False],
        [False, True],
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
    "is_page_content, dirpath, filename, expected",
    [
        [True, "content/pages", "_index", "/pages/"],
        [True, "content/pages", "hx_network", "/pages/hx_network"],
        [
            True,
            "content/pages/lecture-notes",
            "java_3d_lecture",
            "/pages/lecture-notes/java_3d_lecture",
        ],
        [True, "content/resources", "image", "/resources/image"],
        [False, "", "", None],
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
    "is_page_content, dirpath, filename, expected",
    [
        [True, "content/pages", "_index", "content/pages/_index.md"],
        [True, "content/pages", "hx_network", "content/pages/hx_network.md"],
        [
            True,
            "content/pages/lecture-notes",
            "java_3d_lecture",
            "content/pages/lecture-notes/java_3d_lecture.md",
        ],
        [True, "content/resources", "image", "content/resources/image.md"],
        [False, "", "", None],
        [False, "config/_default/menus.yaml", "menus.yaml", None],
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
    for key in default_args.keys():
        value = default_args[key]
        expected_string = f"{key} {value}" if value != "" else key
        if not key in expected_overrides:
            assert expected_string in arg_string
        else:
            assert expected_string not in arg_string
    for key in expected_overrides.keys():
        value = expected_overrides[key]
        expected_string = f"{key} {value}" if value != "" else key
        assert expected_string in arg_string


def test_check_matching_tags():
    """check_matching_tags should throw an exception if the tags don't match"""
    uneven_tags_test_file = os.path.join(
        os.path.dirname(__file__), UNEVEN_TAGS_TEST_FILE
    )
    even_tags_test_file = os.path.join(os.path.dirname(__file__), EVEN_TAGS_TEST_FILE)
    with open(uneven_tags_test_file, encoding="utf-8") as test_config_file:
        test_config = test_config_file.read()
        with pytest.raises(ValueError):
            check_matching_tags(test_config, DEV_START, DEV_END)
        assert check_matching_tags(test_config, NON_DEV_START, NON_DEV_END) is True
    with open(even_tags_test_file, encoding="utf-8") as test_config_file:
        test_config = test_config_file.read()
        assert check_matching_tags(test_config, DEV_START, DEV_END) is True
        assert check_matching_tags(test_config, NON_DEV_START, NON_DEV_END) is True


@pytest.mark.parametrize(
    "start_tag, end_tag, expected",
    [
        [DEV_START, DEV_END, EXPECTED_REMAINING_STRING_DEV],
        [NON_DEV_START, NON_DEV_END, EXPECTED_REMAINING_STRING_NON_DEV],
    ],
)
def test_strip_lines_between(start_tag, end_tag, expected):
    """check that strip_lines_between strips the expected content"""
    even_tags_test_file = os.path.join(os.path.dirname(__file__), EVEN_TAGS_TEST_FILE)
    with open(even_tags_test_file, encoding="utf-8") as test_config_file:
        test_config = test_config_file.read()
        assert expected == strip_lines_between(test_config, start_tag, end_tag)


@pytest.mark.parametrize(
    "start_tag, end_tag",
    [
        ["# DEV START", "# DEV END"],
        ["# STARTT DEV", "# END DEV"],
        ["# START DEV", "# ENDD DEV"],
        ["#START DEV", "# END DEV"],
        ["# START DEV", "#END DEV"],
        ["# START PROD", "# END DEV"],
        ["# START DEV", "# END PROD"],
    ],
)
def test_bad_tags(start_tag, end_tag):
    """make sure errors are thrown if a bad combination of start_tag and end_tag are passed"""
    even_tags_test_file = os.path.join(os.path.dirname(__file__), EVEN_TAGS_TEST_FILE)
    with open(even_tags_test_file, encoding="utf-8") as test_config_file:
        test_config = test_config_file.read()
        with pytest.raises(ValueError):
            check_matching_tags(test_config, start_tag, end_tag)
