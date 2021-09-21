"""Tests for websites API functionality"""
from uuid import UUID

import factory
import pytest

from websites.api import (
    detect_mime_type,
    fetch_website,
    get_valid_new_filename,
    get_valid_new_slug,
    is_ocw_site,
    mail_website_admins_on_publish,
    unassigned_youtube_ids,
    update_youtube_thumbnail,
)
from websites.constants import (
    RESOURCE_TYPE_IMAGE,
    RESOURCE_TYPE_VIDEO,
)
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.messages import (
    PreviewOrPublishFailureMessage,
    PreviewOrPublishSuccessMessage,
)
from websites.models import Website


pytestmark = pytest.mark.django_db

EXAMPLE_UUID_STR = "ae6cfe0b-37a7-4fe6-b194-5b7f1e3c349e"


@pytest.mark.parametrize(
    "existing_filenames,exp_result_filename",
    [
        [[], "my-title"],
        [["my-title"], "my-title2"],
        [["my-title", "my-title9"], "my-title10"],
        [["my-long-title", "my-long-title9"], "my-long-titl10"],
    ],
)
def test_websitecontent_autogen_filename_unique(
    mocker, existing_filenames, exp_result_filename
):
    """
    get_valid_new_filename should return a filename that obeys uniqueness constraints, adding a suffix and
    removing characters from the end of the string as necessary.
    """
    # Set a lower limit for max filename length to test that filenames are truncated appropriately
    mocker.patch("websites.api.CONTENT_FILENAME_MAX_LEN", 14)
    filename_base = (
        exp_result_filename if not existing_filenames else existing_filenames[0]
    )
    content_type = "page"
    dirpath = "path/to"
    website = WebsiteFactory.create()
    WebsiteContentFactory.create_batch(
        len(existing_filenames),
        website=website,
        type=content_type,
        dirpath=dirpath,
        filename=factory.Iterator(existing_filenames),
    )
    assert (
        get_valid_new_filename(
            website_pk=website.pk,
            dirpath=dirpath,
            filename_base=filename_base,
        )
        == exp_result_filename
    )


@pytest.mark.parametrize(
    "uuid_str,filter_value",
    [
        [
            "05d329fd-05ca-4770-b8b2-77ad711daca9",
            "05d329fd-05ca-4770-b8b2-77ad711daca9",
        ],
        ["05d329fd-05ca-4770-b8b2-77ad711daca9", "05d329fd05ca4770b8b277ad711daca9"],
    ],
)
def test_fetch_website_by_uuid(uuid_str, filter_value):
    """fetch_website should find a website based on uuid"""
    website = WebsiteFactory.create(uuid=UUID(uuid_str, version=4))
    result_website = fetch_website(filter_value)
    assert website == result_website


@pytest.mark.parametrize(
    "website_attrs,filter_value",
    [
        [{"title": "my test title"}, "my test title"],
        [{"name": "my test name"}, "my test name"],
        [
            {"title": "05d329fd-05ca-4770-b8b2-77ad711daca9"},
            "05d329fd-05ca-4770-b8b2-77ad711daca9",
        ],
        [
            {"title": "abcdefg1-2345-6789-abcd-123456789abc"},
            "abcdefg1-2345-6789-abcd-123456789abc",
        ],
    ],
)
def test_fetch_website_by_name_title(website_attrs, filter_value):
    """fetch_website should find a website based on a name or title"""
    website = WebsiteFactory.create(
        uuid=UUID(EXAMPLE_UUID_STR, version=4), **website_attrs
    )
    result_website = fetch_website(filter_value)
    assert website == result_website


def test_fetch_website_not_found():
    """fetch_website should raise if a matching website was not found"""
    WebsiteFactory.create(
        uuid=UUID(EXAMPLE_UUID_STR, version=4),
        title="my title",
        name="my name",
    )
    with pytest.raises(Website.DoesNotExist):
        fetch_website("bad values")


@pytest.mark.parametrize(
    "existing_slugs,exp_result_slug",
    [
        [[], "my-slug"],
        [["my-slug"], "my-slug2"],
        [["my-slug", "my-slug9"], "my-slug10"],
        [
            ["very-very-very-very-long-slug", "very-very-very-very-long-slug9"],
            "very-very-very-very-long-slu10",
        ],
    ],
)
def test_websitestarter_autogen_slug_unique(existing_slugs, exp_result_slug):
    """
    get_valid_new_slug should return a slug that obeys uniqueness constraints, adding a suffix and
    removing characters from the end of the string as necessary.
    """
    slug_base = exp_result_slug if not existing_slugs else existing_slugs[0]
    for slug in existing_slugs:
        WebsiteStarterFactory.create(
            path=f"http://github.com/configs1/{slug}",
            slug=slug,
            source="github",
            name=slug,
            config={"collections": []},
        )
    assert (
        get_valid_new_slug(
            slug_base=slug_base, path=f"http://github.com/configs2/{slug_base}"
        )
        == exp_result_slug
    )


def test_is_ocw_site(settings):
    """is_ocw_site() should return expected bool value for a website"""
    settings.OCW_IMPORT_STARTER_SLUG = "ocw-course"
    ocw_site = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(slug="ocw-course")
    )
    other_site = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(slug="not-ocw-course")
    )
    assert is_ocw_site(ocw_site) is True
    assert is_ocw_site(other_site) is False


@pytest.mark.parametrize(
    "youtube_id,existing_thumb,overwrite,expected_thumb",
    [
        [
            None,
            "https://img.youtube.com/fake/0.jpg",
            True,
            "https://img.youtube.com/fake/0.jpg",
        ],
        [
            "abc123",
            "https://img.youtube.com/def456/0.jpg",
            False,
            "https://img.youtube.com/def456/0.jpg",
        ],
        ["abc123", "", False, "https://img.youtube.com/vi/abc123/0.jpg"],
        ["abc123", None, False, "https://img.youtube.com/vi/abc123/0.jpg"],
        [
            "abc123",
            "https://img.youtube.com/def456/0.jpg",
            True,
            "https://img.youtube.com/vi/abc123/0.jpg",
        ],
    ],
)
def test_update_youtube_thumbnail(
    mocker, youtube_id, existing_thumb, overwrite, expected_thumb
):
    """The youtube thumbnail field should be set to the specified value if it exists"""
    mocker.patch("websites.api.is_ocw_site", return_value=True)
    website = WebsiteFactory.create()
    metadata = {
        "video_metadata": {"youtube_id": youtube_id},
        "video_files": {"video_thumbnail_file": existing_thumb},
    }
    update_youtube_thumbnail(website.uuid, metadata, overwrite=overwrite)
    assert metadata["video_files"]["video_thumbnail_file"] == expected_thumb


@pytest.mark.parametrize("is_ocw", [True, False])
def test_unassigned_youtube_ids(mocker, is_ocw):
    """unassigned_youtube_ids should return WebsiteContent objects for videos with no youtube ids"""
    mocker.patch("websites.api.is_ocw_site", return_value=is_ocw)
    website = WebsiteFactory.create()
    WebsiteContentFactory.create_batch(
        3,
        website=website,
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {"youtube_id": "abc123"},
        },
    )
    videos_without_ids = []
    for yt_id in [None, ""]:
        videos_without_ids.append(
            WebsiteContentFactory.create(
                website=website,
                metadata={
                    "resourcetype": RESOURCE_TYPE_VIDEO,
                    "video_metadata": {"youtube_id": yt_id},
                },
            )
        )
    WebsiteContentFactory.create(
        website=website,
        metadata={
            "resourcetype": RESOURCE_TYPE_IMAGE,
            "video_metadata": {"youtube_id": "bad_data"},
        },
    )
    unassigned_content = unassigned_youtube_ids(website)
    if is_ocw:
        assert len(unassigned_content) == 2
        for content in videos_without_ids:
            assert content in unassigned_content
    else:
        assert len(unassigned_content) == 0


@pytest.mark.parametrize("success", [True, False])
@pytest.mark.parametrize("version", ["live", "draft"])
def test_mail_website_admins_on_publish(
    settings, mocker, success, version, permission_groups
):
    """mail_website_admins_on_publish should send correct email to correct users"""
    settings.OCW_STUDIO_LIVE_URL = "http://test.live.edu/"
    settings.OCW_STUDIO_DRAFT_URL = "http://test.draft.edu"
    mock_log = mocker.patch("websites.api.log.error")
    mock_get_message_sender = mocker.patch("websites.api.get_message_sender")
    mock_sender = mock_get_message_sender.return_value.__enter__.return_value
    message = (
        PreviewOrPublishSuccessMessage if success else PreviewOrPublishFailureMessage
    )
    website = permission_groups.websites[0]
    mail_website_admins_on_publish(website, version, success)
    mock_get_message_sender.assert_called_once_with(message)
    if not success:
        mock_log.assert_called_once_with(
            "%s version build failed for site %s", version, website.name
        )
    assert mock_sender.build_and_send_message.call_count == 2
    for user in [website.owner]:
        mock_sender.build_and_send_message.assert_any_call(
            user,
            {
                "site": {
                    "title": website.title,
                    "url": f"http://test.{version}.edu/{website.starter.config['root-url-path']}/{website.name}",
                },
                "version": version,
            },
        )


def test_detect_mime_type(mocker):
    """detect_mime_type should use python-magic to detect the mime type of an uploaded file"""
    chunk = b"chunk"
    chunks_mock = mocker.Mock(return_value=iter([chunk]))
    uploaded_file = mocker.Mock(chunks=chunks_mock)
    mime_type = "image/tiff"
    magic_mock = mocker.patch("websites.api.Magic")
    from_buffer_mock = magic_mock.return_value.from_buffer
    from_buffer_mock.return_value = mime_type

    assert detect_mime_type(uploaded_file) == mime_type
    from_buffer_mock.assert_called_once_with(chunk)
    chunks_mock.assert_called_once_with(chunk_size=2048)
    magic_mock.assert_called_once_with(mime=True)
