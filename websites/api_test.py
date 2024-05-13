"""Tests for websites API functionality"""

from pathlib import Path
from uuid import UUID

import factory
import pytest
import yaml
from django.conf import settings
from mitol.common.utils import now_in_utc

from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from users.factories import UserFactory
from videos.constants import YT_THUMBNAIL_IMG
from websites.api import (
    detect_mime_type,
    fetch_website,
    get_content_warnings,
    get_valid_new_filename,
    get_valid_new_slug,
    get_website_in_root_website_metadata,
    is_ocw_site,
    mail_on_publish,
    update_website_status,
    update_youtube_thumbnail,
    videos_missing_captions,
    videos_with_truncatable_text,
    videos_with_unassigned_youtube_ids,
)
from websites.constants import (
    PUBLISH_STATUS_ERRORED,
    PUBLISH_STATUS_STARTED,
    PUBLISH_STATUS_SUCCEEDED,
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
from websites.serializers_test import VALID_METADATA

pytestmark = pytest.mark.django_db

EXAMPLE_UUID_STR = "ae6cfe0b-37a7-4fe6-b194-5b7f1e3c349e"


@pytest.mark.parametrize("exclude_content", [True, False])
@pytest.mark.parametrize(
    ("filename_base", "existing_filenames", "exp_result_filename"),
    [
        ["my-title", [], "my-title"],  # noqa: PT007
        ["my-title", ["my-title"], "my-title2"],  # noqa: PT007
        ["my-title", ["my-title", "my-title9"], "my-title10"],  # noqa: PT007
        [  # noqa: PT007
            "my-long-title",
            ["my-long-title", "my-long-title9"],
            "my-long-titl10",
        ],
    ],
)
def test_websitecontent_autogen_filename_unique(
    mocker, filename_base, existing_filenames, exp_result_filename, exclude_content
):
    """
    get_valid_new_filename should return a filename that obeys uniqueness constraints, adding a suffix and
    removing characters from the end of the string as necessary.
    """
    # Set a lower limit for max filename length to test that filenames are truncated appropriately
    mocker.patch("websites.api.CONTENT_FILENAME_MAX_LEN", 14)
    content_type = "page"
    dirpath = "path/to"
    website = WebsiteFactory.create()
    contents = WebsiteContentFactory.create_batch(
        len(existing_filenames),
        website=website,
        type=content_type,
        dirpath=dirpath,
        filename=factory.Iterator(existing_filenames),
    )

    exclude_text_id = contents[0].text_id if exclude_content and contents else None

    assert get_valid_new_filename(
        website_pk=website.pk,
        dirpath=dirpath,
        filename_base=filename_base,
        exclude_text_id=exclude_text_id,
    ) == (exp_result_filename if not exclude_content else filename_base)


@pytest.mark.parametrize(
    ("uuid_str", "filter_value"),
    [
        [  # noqa: PT007
            "05d329fd-05ca-4770-b8b2-77ad711daca9",
            "05d329fd-05ca-4770-b8b2-77ad711daca9",
        ],
        [  # noqa: PT007
            "05d329fd-05ca-4770-b8b2-77ad711daca9",
            "05d329fd05ca4770b8b277ad711daca9",
        ],
    ],
)
def test_fetch_website_by_uuid(uuid_str, filter_value):
    """fetch_website should find a website based on uuid"""
    website = WebsiteFactory.create(uuid=UUID(uuid_str, version=4))
    result_website = fetch_website(filter_value)
    assert website == result_website


@pytest.mark.parametrize(
    ("website_attrs", "filter_value"),
    [
        [{"title": "my test title"}, "my test title"],  # noqa: PT007
        [{"name": "my test name"}, "my test name"],  # noqa: PT007
        [{"short_id": "my.test.name"}, "my.test.name"],  # noqa: PT007
        [  # noqa: PT007
            {"title": "05d329fd-05ca-4770-b8b2-77ad711daca9"},
            "05d329fd-05ca-4770-b8b2-77ad711daca9",
        ],
        [  # noqa: PT007
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
    ("existing_slugs", "exp_result_slug"),
    [
        [[], "my-slug"],  # noqa: PT007
        [["my-slug"], "my-slug2"],  # noqa: PT007
        [["my-slug", "my-slug9"], "my-slug10"],  # noqa: PT007
        [  # noqa: PT007
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
    settings.OCW_COURSE_STARTER_SLUG = "ocw-course-v2"
    ocw_site = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(slug="ocw-course-v2")
    )
    other_site = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(slug="not-ocw-course")
    )
    assert is_ocw_site(ocw_site) is True
    assert is_ocw_site(other_site) is False


@pytest.mark.parametrize(
    ("youtube_id", "existing_thumb", "overwrite", "expected_thumb"),
    [
        [  # noqa: PT007
            None,
            YT_THUMBNAIL_IMG.format(video_id="fake"),
            True,
            YT_THUMBNAIL_IMG.format(video_id="fake"),
        ],
        [  # noqa: PT007
            "abc123",
            YT_THUMBNAIL_IMG.format(video_id="def456"),
            False,
            YT_THUMBNAIL_IMG.format(video_id="def456"),
        ],
        [  # noqa: PT007
            "abc123",
            "",
            False,
            YT_THUMBNAIL_IMG.format(video_id="abc123"),
        ],
        [  # noqa: PT007
            "abc123",
            None,
            False,
            YT_THUMBNAIL_IMG.format(video_id="abc123"),
        ],
        [  # noqa: PT007
            "abc123",
            YT_THUMBNAIL_IMG.format(video_id="def456"),
            True,
            YT_THUMBNAIL_IMG.format(video_id="abc123"),
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
    """videos_with_unassigned_youtube_ids should return WebsiteContent objects for videos with no youtube ids"""
    mocker.patch("websites.api.is_ocw_site", return_value=is_ocw)
    website = WebsiteFactory.create()
    WebsiteContentFactory.create_batch(
        4,
        website=website,
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {"youtube_id": "abc123"},
        },
    )
    videos_without_ids = []
    videos_without_ids.append(
        WebsiteContentFactory.create(
            website=website,
            metadata={
                "resourcetype": RESOURCE_TYPE_VIDEO,
                "video_metadata": {},
            },
        )
    )
    for yt_id in [None, ""]:
        videos_without_ids.append(  # noqa: PERF401
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
    unassigned_content = videos_with_unassigned_youtube_ids(website)
    if is_ocw:
        assert len(unassigned_content) == 3
        for content in videos_without_ids:
            assert content in unassigned_content
    else:
        assert len(unassigned_content) == 0


@pytest.mark.parametrize("is_ocw", [True, False])
def test_videos_missing_captions(mocker, is_ocw):
    """videos_missing_captions should return WebsiteContent objects for videos with no captions"""
    mocker.patch("websites.api.is_ocw_site", return_value=is_ocw)
    website = WebsiteFactory.create()
    WebsiteContentFactory.create_batch(
        3,
        website=website,
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_files": {"video_captions_file": "abc123"},
        },
    )
    videos_without_captions = []

    for captions in [None, ""]:
        videos_without_captions.append(  # noqa: PERF401
            WebsiteContentFactory.create(
                website=website,
                metadata={
                    "resourcetype": RESOURCE_TYPE_VIDEO,
                    "video_files": {"video_captions_file": captions},
                },
            )
        )
    WebsiteContentFactory.create(
        website=website,
        metadata={
            "resourcetype": RESOURCE_TYPE_IMAGE,
            "video_files": {"video_captions_file": "bad_data"},
        },
    )

    unassigned_content = videos_missing_captions(website)
    if is_ocw:
        assert len(unassigned_content) == 2
        for content in videos_without_captions:
            assert content in unassigned_content
    else:
        assert len(unassigned_content) == 0


@pytest.mark.parametrize("is_ocw", [True, False])
def test_videos_with_truncatable_text(mocker, is_ocw):
    """Videos with titles or descriptions that are too long should be returned"""
    mocker.patch("websites.api.is_ocw_site", return_value=is_ocw)
    website = WebsiteFactory.create()
    title_descs = (
        (" ".join(["TooLongTitle" for _ in range(10)]), "desc"),
        ("title", " ".join(["TooLongDescription" for _ in range(500)])),
        ("title", "desc"),
    )
    resources = []
    for title, desc in title_descs:
        resources.append(
            WebsiteContentFactory.create(
                website=website,
                title=title,
                metadata={
                    "resourcetype": RESOURCE_TYPE_VIDEO,
                    "video_metadata": {"youtube_description": desc},
                    "video_files": {"video_captions_file": "abc123"},
                },
            )
        )
    truncatable_content = videos_with_truncatable_text(website)
    assert len(resources[1].metadata["video_metadata"]["youtube_description"]) > 5000

    if is_ocw:
        assert len(truncatable_content) == 2
        for content in resources[0:2]:
            assert content in truncatable_content
    else:
        assert truncatable_content == []


@pytest.mark.parametrize("success", [True, False])
@pytest.mark.parametrize("version", ["live", "draft"])
def test_mail_on_publish(settings, mocker, success, version, permission_groups):
    """mail_on_publish should send correct email to correct users"""
    settings.OCW_STUDIO_LIVE_URL = "http://test.live.edu/"
    settings.OCW_STUDIO_DRAFT_URL = "http://test.draft.edu"
    mock_get_message_sender = mocker.patch("websites.api.get_message_sender")
    mock_sender = mock_get_message_sender.return_value.__enter__.return_value
    message = (
        PreviewOrPublishSuccessMessage if success else PreviewOrPublishFailureMessage
    )
    website = permission_groups.websites[0]
    user = UserFactory.create()
    mail_on_publish(website.name, version, success, user.id)
    mock_get_message_sender.assert_called_once_with(message)
    mock_sender.build_and_send_message.assert_any_call(
        user,
        {
            "site": {
                "title": website.title,
                "url": f"http://test.{version}.edu/{website.url_path}",
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


@pytest.mark.parametrize(
    ("status", "notify"),
    [
        [PUBLISH_STATUS_STARTED, False],  # noqa: PT007
        [PUBLISH_STATUS_SUCCEEDED, True],  # noqa: PT007
        [PUBLISH_STATUS_ERRORED, True],  # noqa: PT007
    ],
)
@pytest.mark.parametrize("has_user", [True, False])
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
def test_update_website_status(mocker, status, notify, has_user, version):
    """update_website_status should update the appropriate website publishing fields"""
    mock_mail = mocker.patch("websites.api.mail_on_publish")
    mock_log = mocker.patch("websites.api.log.error")
    user = UserFactory.create() if has_user else None
    website = WebsiteFactory.create(**{f"{version}_last_published_by": user})
    now = now_in_utc()
    update_website_status(website, version, status, now)
    website.refresh_from_db()
    assert getattr(website, f"{version}_publish_status") == status
    assert getattr(website, f"{version}_publish_status_updated_on") == now
    assert mock_mail.call_count == (1 if has_user and notify else 0)
    assert mock_log.call_count == (1 if status == PUBLISH_STATUS_ERRORED else 0)


@pytest.mark.parametrize("status", [PUBLISH_STATUS_SUCCEEDED, PUBLISH_STATUS_ERRORED])
def test_update_website_unpublish_status(mocker, status):
    """update_website_status should update the appropriate website publishing fields"""
    mock_mail = mocker.patch("websites.api.mail_on_publish")
    mock_log = mocker.patch("websites.api.log.error")
    user = UserFactory.create()
    website = WebsiteFactory.create(last_unpublished_by=user, unpublished=True)
    now = now_in_utc()
    update_website_status(website, VERSION_LIVE, status, now, unpublished=True)
    website.refresh_from_db()
    assert website.live_publish_status is None
    assert website.live_publish_status_updated_on is None
    assert website.unpublish_status_updated_on == now
    assert website.unpublish_status == status
    assert mock_mail.call_count == 0
    assert mock_log.call_count == (1 if status == PUBLISH_STATUS_ERRORED else 0)


@pytest.mark.parametrize(
    "status",
    [
        PUBLISH_STATUS_STARTED,
        PUBLISH_STATUS_SUCCEEDED,
        PUBLISH_STATUS_ERRORED,
    ],
)
@pytest.mark.parametrize("version", [VERSION_DRAFT, VERSION_LIVE])
def test_update_unpublished_website_status(status, version):
    """update_website_status should update an unpublished site appropriately"""
    website = WebsiteFactory.create(not_published=True, draft_publish_date=None)
    now = now_in_utc()
    update_website_status(website, version, status, now)
    website.refresh_from_db()
    assert getattr(website, f"{version}_publish_status") == status
    assert getattr(website, f"{version}_publish_status_updated_on") == now

    publish_date_field = (
        "publish_date" if version == VERSION_LIVE else "draft_publish_date"
    )
    if status == PUBLISH_STATUS_SUCCEEDED:
        assert getattr(website, publish_date_field) == now
        if version == VERSION_LIVE:
            assert website.first_published_to_production == now
    else:
        assert getattr(website, publish_date_field) is None


@pytest.mark.parametrize("has_missing_ids", [True, False])
@pytest.mark.parametrize("has_missing_captions", [True, False])
@pytest.mark.parametrize("has_truncatable_text", [True, False])
@pytest.mark.parametrize("is_draft", [True, False])
@pytest.mark.parametrize("valid_metadata", [True, False])
def test_get_content_warnings(  # pylint: disable=too-many-arguments  # noqa: PLR0913
    mocker,
    has_missing_ids,
    has_missing_captions,
    has_truncatable_text,
    is_draft,
    valid_metadata,
):
    """get_content_warnings should return expected warning messages"""
    site_config_path = "localdev/configs/ocw-course-site-config.yml"
    starter = WebsiteStarterFactory(
        config=yaml.load(
            (Path(settings.BASE_DIR) / site_config_path).read_text(),
            Loader=yaml.SafeLoader,
        )
    )
    website = WebsiteFactory.create(starter=starter)
    metadata = {**VALID_METADATA}
    if not valid_metadata:
        del metadata["course_title"]

    WebsiteContentFactory.create(
        type="sitemetadata", website=website, metadata=metadata
    )
    video_content = WebsiteContentFactory.create_batch(3, website=website)
    no_yt_ids = video_content[0:2] if has_missing_ids else []
    no_caps = video_content[1:3] if has_missing_captions else []
    truncatable_vids = [video_content[2]] if has_truncatable_text else []
    # testing only for videos here, but warnings will be the same for any content type
    draft_titles = [video_content[1]] if is_draft else []
    mocker.patch(
        "websites.api.videos_with_truncatable_text", return_value=truncatable_vids
    )
    mocker.patch(
        "websites.api.videos_with_unassigned_youtube_ids",
        return_value=no_yt_ids,
    )
    mocker.patch(
        "websites.api.videos_missing_captions",
        return_value=no_caps,
    )
    mocker.patch(
        "websites.api.draft_content",
        return_value=draft_titles,
    )
    warnings = get_content_warnings(website)
    warnings_len = 0
    if not valid_metadata:
        warnings_len += 1
    if has_missing_ids:
        warnings_len += 1
        for content in no_yt_ids:
            assert content.title in warnings[1 if not valid_metadata else 0]
    if has_missing_captions:
        warnings_len += 1
        for content in no_caps:
            assert (
                content.title
                in warnings[int(not valid_metadata) + int(has_missing_ids)]
            )
    if has_truncatable_text:
        warnings_len += 1
        assert (
            video_content[2].title
            in warnings[
                int(not valid_metadata)
                + int(has_missing_ids)
                + int(has_missing_captions)
            ]
        )
    if is_draft:
        warnings_len += 1
        assert len(warnings) == warnings_len
        assert video_content[1].title in warnings[warnings_len - 1]
    if (
        valid_metadata
        and not has_missing_ids
        and not has_missing_captions
        and not has_truncatable_text
        and not is_draft
    ):
        assert not warnings


@pytest.mark.parametrize(
    ("version", "site_fields", "expected_draft"),
    [
        (
            # Publishing to live, but site previously published live.
            VERSION_LIVE,
            {},
            False,
        ),
        (
            # Publishing to live for first time
            VERSION_LIVE,
            {"publish_date": None},
            False,
        ),
        (
            # Publishing to draft, but site previously published live.
            VERSION_DRAFT,
            {"publish_date": now_in_utc()},
            False,
        ),
        (
            # Site is unbpublished.
            VERSION_DRAFT,
            {"unpublish_status": PUBLISH_STATUS_SUCCEEDED},
            True,
        ),
        (
            # Site is unbpublished.
            VERSION_LIVE,
            {"unpublish_status": PUBLISH_STATUS_SUCCEEDED},
            True,
        ),
        (
            # Site never published. OK to set to draft
            VERSION_DRAFT,
            {"publish_date": None},
            True,
        ),
    ],
)
def test_get_website_in_root_website_metadata(version, site_fields, expected_draft):
    """
    Test that get_website_in_root_website_metadata returns the expected metadata,
    especially in regards to draft status.
    """
    website = WebsiteFactory.create(**site_fields)
    sitemetadata = WebsiteContentFactory.create(
        website=website,
        type="sitemetadata",
        metadata={
            "some": "field",
        },
    )

    expected = {
        **sitemetadata.metadata,
        "url_path": website.url_path,
        "_build": {"list": True, "render": False},
    }
    if expected_draft:
        expected["draft"] = True

    assert get_website_in_root_website_metadata(website, version) == expected
