"""
Tests for youtube api
"""
import random
import string
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from googleapiclient.errors import HttpError

from content_sync.constants import VERSION_DRAFT, VERSION_LIVE
from users.factories import UserFactory
from videos.conftest import MockHttpErrorResponse
from videos.constants import DESTINATION_YOUTUBE
from videos.factories import VideoFactory, VideoFileFactory
from videos.messages import YouTubeUploadFailureMessage, YouTubeUploadSuccessMessage
from videos.youtube import (
    CAPTION_UPLOAD_NAME,
    YouTubeApi,
    YouTubeUploadException,
    mail_youtube_upload_failure,
    mail_youtube_upload_success,
    strip_bad_chars,
    update_youtube_metadata,
)
from websites.constants import (
    CONTENT_TYPE_RESOURCE,
    RESOURCE_TYPE_IMAGE,
    RESOURCE_TYPE_VIDEO,
)
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.models import WebsiteContent


pytestmark = pytest.mark.django_db

# pylint: disable=redefined-outer-name,unused-argument,no-value-for-parameter,unused-variable


@pytest.fixture
def youtube_mocker(mocker):
    """Return a mock youtube api client"""
    return mocker.patch("videos.youtube.build")


@pytest.fixture
def mock_mail(mocker):
    """ Objects and mocked functions for mail tests"""
    mock_get_message_sender = mocker.patch("videos.youtube.get_message_sender")
    mock_sender = mock_get_message_sender.return_value.__enter__.return_value
    video_file = VideoFileFactory.create()
    users = UserFactory.create_batch(4)
    for user in users[:2]:
        user.groups.add(video_file.video.website.admin_group)
    for user in users[2:]:
        user.groups.add(video_file.video.website.editor_group)
    return SimpleNamespace(
        mock_get_message_sender=mock_get_message_sender,
        mock_sender=mock_sender,
        video_file=video_file,
        users=users,
    )


def test_youtube_settings(mocker, settings):
    """
    Test that Youtube object creation uses YT_* settings for credentials
    """
    settings.YT_ACCESS_TOKEN = "yt_access_token"
    settings.YT_CLIENT_ID = "yt_client_id"
    settings.YT_CLIENT_SECRET = "yt_secret"
    settings.YT_REFRESH_TOKEN = "yt_refresh"
    mock_oauth = mocker.patch("videos.youtube.oauth2client.client.GoogleCredentials")
    YouTubeApi()
    mock_oauth.assert_called_with(
        settings.YT_ACCESS_TOKEN,
        settings.YT_CLIENT_ID,
        settings.YT_CLIENT_SECRET,
        settings.YT_REFRESH_TOKEN,
        None,
        "https://accounts.google.com/o/oauth2/token",
        None,
    )


def test_upload_video(youtube_mocker):
    """
    Test that the upload_video task calls the YouTube API execute method
    """
    videofile = VideoFileFactory()
    youtube_id = "M6LymW_8qVk"
    video_upload_response = {
        "id": youtube_id,
        "kind": "youtube#video",
        "snippet": {"description": "Testing description", "title": "Testing123"},
        "status": {"uploadStatus": "uploaded"},
    }
    youtube_mocker().videos.return_value.insert.return_value.next_chunk.side_effect = [
        (None, None),
        (None, video_upload_response),
    ]
    response = YouTubeApi().upload_video(videofile)
    assert response == video_upload_response


def test_upload_video_no_id(youtube_mocker):
    """
    Test that the upload_video task fails if the response contains no id
    """
    videofile = VideoFileFactory()
    youtube_mocker().videos.return_value.insert.return_value.next_chunk.return_value = (
        None,
        {},
    )
    with pytest.raises(YouTubeUploadException):
        YouTubeApi().upload_video(videofile)


@pytest.mark.parametrize(
    ["error", "retryable"],
    [
        [HttpError(MockHttpErrorResponse(500), b""), True],
        [HttpError(MockHttpErrorResponse(403), b""), False],
        [OSError, True],
        [IndexError, False],
    ],
)
def test_upload_errors_retryable(mocker, youtube_mocker, error, retryable):
    """
    Test that uploads are retried 10x for retryable exceptions
    """
    mocker.patch("videos.youtube.time")
    videofile = VideoFileFactory()
    youtube_mocker().videos.return_value.insert.return_value.next_chunk.side_effect = (
        error
    )
    with pytest.raises(Exception) as exc:
        YouTubeApi().upload_video(videofile)
    assert str(exc.value).startswith("Retried YouTube upload 10x") == retryable


def test_upload_video_long_fields(mocker, youtube_mocker):
    """
    Test that the upload_youtube_video task truncates title and description if too long
    """
    name = "".join(random.choice(string.ascii_lowercase) for c in range(105))
    video_file = VideoFileFactory.create()
    video_file.video.source_key = video_file.s3_key.replace("file_", name)
    mocker.patch("videos.youtube.resumable_upload")
    mock_upload = youtube_mocker().videos.return_value.insert
    YouTubeApi().upload_video(video_file)
    called_args, called_kwargs = mock_upload.call_args
    assert called_kwargs["body"]["snippet"]["title"] == name[:100]


def test_delete_video(youtube_mocker):
    """
    Test that the 'delete_video' method executes a YouTube API deletion request and returns the status code
    """
    youtube_mocker().videos.return_value.delete.return_value.execute.return_value = 204
    assert YouTubeApi().delete_video("foo") == 204
    youtube_mocker().videos.return_value.delete.assert_called_with(id="foo")


@pytest.mark.parametrize("privacy", [None, "public"])
def test_update_video(settings, mocker, youtube_mocker, privacy):
    """update_video should send the correct data in a request to update youtube metadata"""
    speakers = "speaker1, speaker2"
    tags = "tag1, tag2"
    youtube_id = "abc123"
    description = "video test description"
    content = WebsiteContentFactory.create(
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "description": description,
            "video_metadata": {
                "youtube_id": youtube_id,
                "video_tags": tags,
                "video_speakers": speakers,
            },
        }
    )

    mock_update_caption = mocker.patch("videos.youtube.YouTubeApi.update_captions")

    YouTubeApi().update_video(content, privacy=privacy)
    youtube_mocker().videos.return_value.update.assert_any_call(
        part="snippet",
        body={
            "id": youtube_id,
            "snippet": {
                "title": content.title,
                "description": f"{description}\n\nSpeakers: {speakers}",
                "tags": tags,
                "categoryId": settings.YT_CATEGORY_ID,
            },
        },
    )
    if privacy is not None:
        youtube_mocker().videos.return_value.update.assert_any_call(
            part="status",
            body={
                "id": youtube_id,
                "status": {"privacyStatus": privacy, "embeddable": True},
            },
        )

    mock_update_caption.assert_called_once_with(content, youtube_id)


def test_video_status(youtube_mocker):
    """
    Test that the 'video_status' method returns the correct value from the API response
    """
    expected_status = "processed"
    youtube_mocker().videos.return_value.list.return_value.execute.return_value = {
        "etag": '"ld9biNPKjAjgjV7EZ4EKeEGrhao/Lf7oS5V-Gjw0XHBBKFJRpn60z3w"',
        "items": [
            {
                "etag": '"ld9biNPKjAjgjV7EZ4EKeEGrhao/-UL82wRXbq3YJiMZuZpqCWKoq6Q"',
                "id": "wAjoqsZng_M",
                "kind": "youtube#video",
                "status": {
                    "embeddable": True,
                    "license": "youtube",
                    "privacyStatus": "unlisted",
                    "publicStatsViewable": True,
                    "uploadStatus": expected_status,
                },
            }
        ],
        "kind": "youtube#videoListResponse",
        "pageInfo": {"resultsPerPage": 1, "totalResults": 1},
    }
    assert YouTubeApi().video_status("foo") == expected_status
    youtube_mocker().videos.return_value.list.assert_called_once_with(
        id="foo", part="status"
    )


def test_strip_bad_chars():
    """
    Test that `<`,`>` characters are removed from text
    """
    assert strip_bad_chars("<OV>S>") == "OVS"


def test_mail_youtube_upload_failure(settings, mock_mail):
    """Test that the appropriate mail functions are called with correct args"""
    mail_youtube_upload_failure(mock_mail.video_file)
    mock_mail.mock_get_message_sender.assert_called_once_with(
        YouTubeUploadFailureMessage
    )
    assert (
        mock_mail.mock_sender.build_and_send_message.call_count
        == len(mock_mail.users) + 1
    )
    website = mock_mail.video_file.video.website
    for collaborator in website.collaborators:
        mock_mail.mock_sender.build_and_send_message.assert_any_call(
            collaborator,
            {
                "site": {
                    "title": website.title,
                    "url": f"{settings.SITE_BASE_URL}sites/{website.name}",
                },
                "video": {
                    "filename": mock_mail.video_file.video.source_key.split("/")[-1]
                },
            },
        )


def test_mail_youtube_upload_success(settings, mock_mail):
    """Test that the appropriate mail functions are called with correct args"""
    mail_youtube_upload_success(mock_mail.video_file)
    mock_mail.mock_get_message_sender.assert_called_once_with(
        YouTubeUploadSuccessMessage
    )
    assert (
        mock_mail.mock_sender.build_and_send_message.call_count
        == len(mock_mail.users) + 1
    )
    website = mock_mail.video_file.video.website
    for collaborator in website.collaborators:
        mock_mail.mock_sender.build_and_send_message.assert_any_call(
            collaborator,
            {
                "site": {
                    "title": website.title,
                    "url": f"{settings.SITE_BASE_URL}sites/{website.name}",
                },
                "video": {
                    "filename": mock_mail.video_file.video.source_key.split("/")[-1],
                    "url": f"https://www.youtube.com/watch?v={mock_mail.video_file.destination_id}",
                },
            },
        )


@pytest.mark.parametrize("video_file_exists", [True, False])
@pytest.mark.parametrize("youtube_enabled", [True, False])
@pytest.mark.parametrize("is_ocw", [True, False])
@pytest.mark.parametrize(
    "version, privacy", [[VERSION_DRAFT, None], [VERSION_LIVE, "public"]]
)
def test_update_youtube_metadata(  # pylint:disable=too-many-arguments
    mocker,
    settings,
    video_file_exists,
    youtube_enabled,
    is_ocw,
    version,
    privacy,
):
    """ Check that youtube.update_video is called for appropriate resources and not others"""
    mock_youtube = mocker.patch("videos.youtube.YouTubeApi")
    mock_update_video = mock_youtube.return_value.update_video
    mocker.patch("videos.youtube.is_ocw_site", return_value=is_ocw)
    mocker.patch("videos.youtube.is_youtube_enabled", return_value=youtube_enabled)
    website = WebsiteFactory.create()
    WebsiteContentFactory.create(
        type=CONTENT_TYPE_RESOURCE,
        metadata={
            "resourcetype": RESOURCE_TYPE_IMAGE,
            "video_metadata": {"youtube_id": "fakeid"},
        },
    )
    for youtube_id in ["", None, "abc123", "def456"]:
        WebsiteContentFactory.create(
            website=website,
            type=CONTENT_TYPE_RESOURCE,
            metadata={
                "resourcetype": RESOURCE_TYPE_VIDEO,
                "video_metadata": {"youtube_id": youtube_id},
            },
        )
        if video_file_exists:
            VideoFileFactory.create(
                video=VideoFactory.create(website=website),
                destination=DESTINATION_YOUTUBE,
                destination_id=youtube_id,
            )
    update_youtube_metadata(website, version=version)
    if youtube_enabled and is_ocw:
        mock_youtube.assert_called_once()
        # Don't update metadata for imported ocw course videos except on production
        if video_file_exists:
            assert mock_update_video.call_count == 2
            for youtube_id in ["abc123", "def456"]:
                mock_update_video.assert_any_call(
                    WebsiteContent.objects.get(
                        website=website, metadata__video_metadata__youtube_id=youtube_id
                    ),
                    privacy=privacy,
                )
        else:
            mock_update_video.assert_not_called()
    else:
        mock_update_video.assert_not_called()


def test_update_youtube_metadata_no_videos(mocker):
    """Youtube API should not be instantiated if there are no videos"""
    mocker.patch("videos.youtube.is_ocw_site", return_value=True)
    mocker.patch("videos.youtube.is_youtube_enabled", return_value=True)
    mock_youtube = mocker.patch("videos.youtube.YouTubeApi")
    update_youtube_metadata(WebsiteFactory.create())
    mock_youtube.assert_not_called()


@pytest.mark.parametrize("existing_captions", [True, False])
def test_update_captions(settings, mocker, youtube_mocker, existing_captions):
    """
    Test update_captions
    """
    youtube_id = "abc123"
    captions = b"these are the file contents!"

    videofile = VideoFileFactory.create(
        destination=DESTINATION_YOUTUBE, destination_id=youtube_id
    )
    video = videofile.video

    video.webvtt_transcript_file = SimpleUploadedFile("file.txt", captions)
    video.save()

    content = WebsiteContentFactory.create(
        metadata={
            "resourcetype": RESOURCE_TYPE_VIDEO,
            "video_metadata": {
                "youtube_id": youtube_id,
            },
        },
        website=video.website,
    )

    if existing_captions:
        existing_captions_response = {
            "items": [
                {"id": "youtube_caption_id", "snippet": {"name": CAPTION_UPLOAD_NAME}}
            ]
        }
    else:
        existing_captions_response = {"items": []}

    mock_media_upload = mocker.patch("videos.youtube.MediaIoBaseUpload")
    mock_bytes_io = mocker.patch("videos.youtube.BytesIO")

    youtube_mocker().captions.return_value.list.return_value.execute.return_value = (
        existing_captions_response
    )

    YouTubeApi().update_captions(content, youtube_id)
    youtube_mocker().captions.return_value.list.assert_any_call(
        part="snippet", videoId=youtube_id
    )

    mock_bytes_io.assert_called_once_with(captions)

    mock_media_upload.assert_called_once_with(
        mock_bytes_io.return_value, mimetype="text/vtt", chunksize=-1, resumable=True
    )

    if existing_captions:
        youtube_mocker().captions.return_value.update.assert_any_call(
            part="snippet",
            body={"id": "youtube_caption_id"},
            media_body=mock_media_upload.return_value,
        )
    else:
        youtube_mocker().captions.return_value.insert.assert_any_call(
            part="snippet",
            sync=False,
            body={
                "snippet": {
                    "language": "en",
                    "name": CAPTION_UPLOAD_NAME,
                    "videoId": youtube_id,
                }
            },
            media_body=mock_media_upload.return_value,
        )
