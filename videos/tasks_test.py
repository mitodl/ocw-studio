""" videos.tasks tests"""
import string
from datetime import datetime
from random import choice
from urllib.parse import urljoin

import pytest
import pytz
from django.conf import settings
from googleapiclient.errors import HttpError, ResumableUploadError
from moto import mock_s3

from gdrive_sync.api import create_gdrive_resource_content
from gdrive_sync.factories import DriveFileFactory
from main.s3_utils import get_boto3_client
from ocw_import.conftest import MOCK_BUCKET_NAME, setup_s3
from users.factories import UserFactory
from videos.conftest import MockHttpErrorResponse
from videos.constants import (
    DESTINATION_YOUTUBE,
    YT_THUMBNAIL_IMG,
    VideoFileStatus,
    VideoStatus,
    YouTubeStatus,
)
from videos.factories import VideoFactory, VideoFileFactory
from videos.models import VideoFile
from videos.tasks import (
    attempt_to_update_missing_transcripts,
    delete_s3_objects,
    mail_transcripts_complete_notification,
    remove_youtube_video,
    start_transcript_job,
    update_transcripts_for_updated_videos,
    update_transcripts_for_video,
    update_transcripts_for_website,
    update_youtube_statuses,
    upload_youtube_videos,
)
from videos.youtube import API_QUOTA_ERROR_MSG
from websites.constants import RESOURCE_TYPE_VIDEO
from websites.factories import WebsiteContentFactory, WebsiteFactory
from websites.messages import VideoTranscriptingCompleteMessage
from websites.utils import get_dict_field, set_dict_field


# pylint:disable=unused-argument,redefined-outer-name
pytestmark = pytest.mark.django_db


def create_video(youtube_id, title):
    """
    Creates video file with the given youtube_id and title.
    """
    video_file = VideoFileFactory.create(
        status=VideoStatus.CREATED,
        destination=DESTINATION_YOUTUBE,
        destination_id=youtube_id,
    )

    video = video_file.video
    video.source_key = "the/file"
    video.save()

    return video


def create_content(website, youtube_id, title):
    """
    Creates website content with the given website, YouTube ID, and title.
    """
    return WebsiteContentFactory.create(
        website=website,
        metadata={"video_metadata": {"youtube_id": youtube_id}},
        title=title,
    )


def set_nested_dicts(obj, field_path, value):
    """Set the value of a potentially nested dict path"""
    fields = field_path.split(".")
    current_obj = obj
    for field in fields[:-1]:
        current_obj[field] = {}
        current_obj = current_obj[field]

    current_obj[fields[-1]] = value


def updated_transctipts_reponse():
    """Mock api response for s3 updated transcripts api call"""
    return {
        "code": 200,
        "data": [
            {
                "id": 6737396,
                "name": "12. Carbohydrates/Introduction to Membranes\n",
                "duration": 10.0,
                "word_count": 16,
                "language_id": 1,
                "language_ids": [1],
                "source": "https://www.youtube.com/watch?v=test",
                "batch_id": 200797,
                "reference_id": "reference_id",
                "labels": ["updated"],
                "created_at": "2021-08-19T10:43:26.000-04:00",
                "updated_at": "2021-09-01T21:14:19.000-04:00",
            }
        ],
        "pagination": {"page": 1, "per_page": 25, "total_entries": 1},
    }


@pytest.fixture
def youtube_video_files_new():
    """Return 3 Youtube video files"""
    return VideoFileFactory.create_batch(
        3,
        status=VideoStatus.CREATED,
        destination=DESTINATION_YOUTUBE,
        destination_id=None,
    )


@pytest.fixture
def youtube_video_files_processing():
    """Return 3 Youtube video files"""
    return VideoFileFactory.create_batch(
        3,
        status=VideoFileStatus.UPLOADED,
        destination=DESTINATION_YOUTUBE,
        destination_status=YouTubeStatus.PROCESSING,
    )


@pytest.mark.parametrize("is_enabled", [True, False])
@pytest.mark.parametrize("max_uploads", [2, 4])
def test_upload_youtube_videos(
    mocker, youtube_video_files_new, max_uploads, is_enabled, mocked_celery
):
    """
    Test that the upload_youtube_videos task calls YouTubeApi.upload_video
    & creates a YoutubeVideo object for each public video, up to the max daily limit
    """
    if not is_enabled:
        settings.YT_CLIENT_ID = None
    settings.YT_UPLOAD_LIMIT = max_uploads
    mock_youtube = mocker.patch("videos.tasks.YouTubeApi")
    mock_uploader = mock_youtube.return_value.upload_video
    mock_uploader.return_value = {
        "id": "".join([choice(string.ascii_lowercase) for n in range(8)]),
        "status": {"uploadStatus": "uploaded"},
    }

    upload_youtube_videos.delay()
    assert mock_uploader.call_count == (min(3, max_uploads) if is_enabled else 0)
    assert mock_youtube.call_count == (1 if is_enabled else 0)
    if is_enabled:
        for video_file in VideoFile.objects.order_by("-created_on")[
            : settings.YT_UPLOAD_LIMIT
        ]:
            assert video_file.destination_id is not None
            assert video_file.destination_status == YouTubeStatus.UPLOADED
            assert video_file.status == VideoFileStatus.UPLOADED


def test_upload_youtube_videos_error(mocker, youtube_video_files_new):
    """
    Test that the VideoFile status is set properly if an error occurs during upload, and all videos are processed
    """
    mock_uploader = mocker.patch(
        "videos.tasks.YouTubeApi.upload_video", side_effect=OSError
    )
    upload_youtube_videos.delay()
    assert mock_uploader.call_count == 3
    for video_file in youtube_video_files_new:
        video_file.refresh_from_db()
        assert video_file.status == VideoFileStatus.FAILED


def test_upload_youtube_videos_no_videos(mocker):
    """YouTube API shoould not be instantiated if there are no videos to upload"""
    mock_youtube = mocker.patch("videos.tasks.YouTubeApi")

    upload_youtube_videos.delay()
    mock_youtube.assert_not_called()


@pytest.mark.parametrize(
    "msg,status",
    [
        [API_QUOTA_ERROR_MSG, VideoFileStatus.CREATED],
        ["other error", VideoFileStatus.FAILED],
    ],
)
def test_upload_youtube_quota_exceeded(mocker, youtube_video_files_new, msg, status):
    """
    Test that the YoutubeVideo object is deleted if an error occurs during upload,
    and the loop is halted if the quota is exceeded.
    """
    mock_uploader = mocker.patch(
        "videos.tasks.YouTubeApi.upload_video",
        side_effect=ResumableUploadError(
            MockHttpErrorResponse(403), str.encode(msg, "utf-8")
        ),
    )
    upload_youtube_videos.delay()
    assert mock_uploader.call_count == (1 if msg == API_QUOTA_ERROR_MSG else 3)
    for video_file in youtube_video_files_new:
        video_file.refresh_from_db()
        assert video_file.status == status
        assert video_file.destination_status is None
        assert video_file.destination_id is None


@pytest.mark.parametrize("wrong_caption_type", [True, False])
@pytest.mark.parametrize("caption_exists", [True, False])
@pytest.mark.parametrize("transcript_exists", [True, False])
def test_start_transcript_job(
    mocker, settings, caption_exists, transcript_exists, wrong_caption_type
):
    """test start_transcript_job"""
    youtube_id = "test"
    threeplay_file_id = 1
    settings.YT_FIELD_ID = "video_metadata.youtube_id"
    title = "title"

    video = create_video(youtube_id, title)
    video_content = create_content(video.website, youtube_id, title)

    base_path = f"/some/path/to/{video_content.filename}"

    if wrong_caption_type:
        WebsiteContentFactory.create(
            website=video.website,
            filename=f"{video_content.filename}_captions",
            file=f"{base_path}_captions.srt",
        )

    if caption_exists:
        WebsiteContentFactory.create(
            website=video.website,
            filename=f"{video_content.filename}_captions",
            file=f"{base_path}_captions.vtt",
        )

    if transcript_exists:
        WebsiteContentFactory.create(
            website=video.website,
            filename=f"{video_content.filename}_transcript",
            file=f"{base_path}_transcript.pdf",
        )

    mock_threeplay_upload_video_request = mocker.patch(
        "videos.tasks.threeplay_api.threeplay_upload_video_request",
        return_value={"data": {"id": threeplay_file_id}},
    )

    mock_order_transcript_request_request = mocker.patch(
        "videos.tasks.threeplay_api.threeplay_order_transcript_request"
    )

    start_transcript_job(video.id)

    video_content.refresh_from_db()
    assert get_dict_field(video_content.metadata, settings.YT_FIELD_CAPTIONS) == (
        f"{base_path}_captions.vtt" if caption_exists else None
    )
    assert get_dict_field(video_content.metadata, settings.YT_FIELD_TRANSCRIPT) == (
        f"{base_path}_transcript.pdf" if transcript_exists else None
    )

    if transcript_exists or caption_exists:
        mock_threeplay_upload_video_request.assert_not_called()
        mock_order_transcript_request_request.assert_not_called()
        return

    mock_threeplay_upload_video_request.assert_called_once_with(
        video.website.short_id, youtube_id, title
    )
    if video.status != VideoStatus.SUBMITTED_FOR_TRANSCRIPTION:
        mock_order_transcript_request_request.assert_called_once_with(
            video.id, threeplay_file_id
        )
    else:
        mock_order_transcript_request_request.assert_not_called()


# pylint:disable=unused-argument,redefined-outer-name
def test_threeplay_submission_called_once_per_video(mocker, settings):
    """
    Test that the threeplay_submission function is called only once per video.
    """
    youtube_id = "test"
    threeplay_file_id = 1
    settings.YT_FIELD_ID = "video_metadata.youtube_id"
    title = "title"

    video = create_video(youtube_id, title)
    video_content = create_content(video.website, youtube_id, title)

    mock_threeplay_upload_video_request = mocker.patch(
        "videos.tasks.threeplay_api.threeplay_upload_video_request",
        return_value={"data": {"id": 1}},
    )

    mock_order_transcript_request_request = mocker.patch(
        "videos.tasks.threeplay_api.threeplay_order_transcript_request"
    )

    start_transcript_job(video.id)
    start_transcript_job(video.id)

    if video.status != VideoStatus.SUBMITTED_FOR_TRANSCRIPTION:
        mock_order_transcript_request_request.assert_called_once_with(
            video.id, threeplay_file_id
        )
    else:
        mock_order_transcript_request_request.assert_not_called()


@pytest.mark.parametrize("is_enabled", [True, False])
def test_update_youtube_statuses(  # pylint:disable=too-many-arguments
    settings,
    mocker,
    youtube_video_files_processing,
    youtube_video_files_new,
    is_enabled,
    mocked_celery,
):
    """
    Test that the correct number of YouTubeVideo objects have their statuses updated to the correct value.
    """
    if not is_enabled:
        settings.YT_CLIENT_ID = None
    mock_youtube = mocker.patch("videos.tasks.YouTubeApi")
    mock_youtube.return_value.video_status.return_value = YouTubeStatus.PROCESSED
    mock_mail_youtube_upload_success = mocker.patch(
        "videos.tasks.mail_youtube_upload_success"
    )
    mocker.patch("gdrive_sync.api.get_resource_type", return_value=RESOURCE_TYPE_VIDEO)
    for video_file in youtube_video_files_processing:
        drive_file = DriveFileFactory.create(video=video_file.video)
        create_gdrive_resource_content(drive_file)
    mock_transcript_job = mocker.patch("videos.tasks.start_transcript_job.s")
    if is_enabled:
        with pytest.raises(mocked_celery.replace_exception_class):
            update_youtube_statuses.delay()
    else:
        update_youtube_statuses.delay()
    assert VideoFile.objects.filter(
        destination_status=YouTubeStatus.PROCESSED, status=VideoFileStatus.COMPLETE
    ).count() == (3 if is_enabled else 0)
    if is_enabled:
        mock_youtube.assert_called_once()

        for video_file in youtube_video_files_processing:
            mock_mail_youtube_upload_success.assert_any_call(video_file)
            assert video_file.video.drivefile_set.first().resource.metadata == {
                "resourcetype": "Video",
                "file_type": video_file.video.drivefile_set.first().mime_type,
                "video_files": {
                    "video_thumbnail_file": YT_THUMBNAIL_IMG.format(
                        video_id=video_file.destination_id
                    )
                },
                "video_metadata": {"youtube_id": video_file.destination_id},
                "image": "",
                "license": "default_license_specificed_in_config",
            }
            mock_transcript_job.assert_any_call(video_file.video.id)
    else:
        mock_youtube.assert_not_called()
        mock_mail_youtube_upload_success.assert_not_called()


def test_update_youtube_statuses_api_quota_exceeded(
    mocker, youtube_video_files_processing
):
    """
    Test that the update_youtube_statuses task stops without raising an error if the API quota is exceeded.
    """
    mock_video_status = mocker.patch(
        "videos.tasks.YouTubeApi.video_status",
        side_effect=HttpError(
            MockHttpErrorResponse(403), str.encode(API_QUOTA_ERROR_MSG, "utf-8")
        ),
    )
    update_youtube_statuses.delay()
    mock_video_status.assert_called_once()


def test_update_youtube_statuses_http_error(mocker, youtube_video_files_processing):
    """
    Test that an error is raised if any http error occurs other than exceeding daily API quota
    """
    mock_video_status = mocker.patch(
        "videos.tasks.YouTubeApi.video_status",
        side_effect=HttpError(MockHttpErrorResponse(403), b"other error"),
    )
    mock_mail_youtube_upload_failure = mocker.patch(
        "videos.tasks.mail_youtube_upload_failure"
    )
    mock_log = mocker.patch("videos.tasks.log.exception")
    update_youtube_statuses.delay()
    for video_file in youtube_video_files_processing:
        mock_video_status.assert_any_call(video_file.destination_id)
        mock_log.assert_any_call(
            "Error for youtube_id %s: %s", video_file.destination_id, "other error"
        )
        mock_mail_youtube_upload_failure.assert_any_call(video_file)


def test_update_youtube_statuses_index_error(mocker, youtube_video_files_processing):
    """
    Test that an error is raised if a index error occurs
    """
    mock_log = mocker.patch("videos.tasks.log.exception")
    mocker.patch(
        "videos.tasks.YouTubeApi.video_status",
        side_effect=IndexError(),
    )
    mock_mail_youtube_upload_failure = mocker.patch(
        "videos.tasks.mail_youtube_upload_failure"
    )
    update_youtube_statuses.delay()
    for video_file in youtube_video_files_processing:
        mock_log.assert_any_call(
            "Status of YouTube video not found: youtube_id %s",
            video_file.destination_id,
        )
        mock_mail_youtube_upload_failure.assert_any_call(video_file)


def test_update_youtube_statuses_no_videos(mocker):
    """Youtube API should not be instantiated if there are no videos to process"""
    mock_youtube = mocker.patch("videos.tasks.YouTubeApi")
    update_youtube_statuses.delay()
    mock_youtube.assert_not_called()


@pytest.mark.parametrize("is_enabled", [True, False])
def test_remove_youtube_video(
    settings, mocker, youtube_video_files_processing, is_enabled
):
    """Verify that remove_youtube_video makes the appropriate api call to delete a video"""
    if not is_enabled:
        settings.YT_CLIENT_ID = None
    mock_delete = mocker.patch("videos.tasks.YouTubeApi.delete_video")
    video_file = youtube_video_files_processing[0]
    remove_youtube_video(video_file.destination_id)
    if is_enabled:
        mock_delete.assert_called_once_with(video_file.destination_id)
    else:
        mock_delete.assert_not_called()


def test_remove_youtube_video_404_error(mocker, youtube_video_files_processing):
    """Test that a 404 http error is handled appropriately and logged"""
    mock_log = mocker.patch("videos.tasks.log.info")
    mocker.patch(
        "videos.tasks.YouTubeApi.delete_video",
        side_effect=HttpError(MockHttpErrorResponse(404), b"error"),
    )
    video_file = youtube_video_files_processing[0]
    remove_youtube_video(video_file.destination_id)
    mock_log.assert_called_once_with(
        "Not found on Youtube, already deleted?", video_id=video_file.destination_id
    )


def test_remove_youtube_video_other_http_error(mocker, youtube_video_files_processing):
    """Test that a non-404 http error is raised"""
    mocker.patch(
        "videos.tasks.YouTubeApi.delete_video",
        side_effect=HttpError(MockHttpErrorResponse(500), b"error"),
    )
    video_file = youtube_video_files_processing[0]
    with pytest.raises(HttpError):
        remove_youtube_video(video_file.destination_id)


@mock_s3
def test_delete_s3_objects(settings):
    """Test that s3 objects are deleted"""
    settings.AWS_STORAGE_BUCKET_NAME = MOCK_BUCKET_NAME
    setup_s3(settings)
    client = get_boto3_client("s3")
    assert (
        client.get_object(
            Bucket=MOCK_BUCKET_NAME, Key="biology/config/_default/menus.yaml"
        )
        is not None
    )
    assert (
        client.get_object(
            Bucket=MOCK_BUCKET_NAME, Key="biology/content/resources/biology.md"
        )
        is not None
    )
    delete_s3_objects(key="biology/config/_default/menus.yaml")
    with pytest.raises(client.exceptions.NoSuchKey):
        assert client.get_object(
            Bucket=MOCK_BUCKET_NAME, Key="biology/config/_default/menus.yaml"
        )
    assert (
        client.get_object(
            Bucket=MOCK_BUCKET_NAME, Key="biology/content/resources/biology.md"
        )
        is not None
    )
    delete_s3_objects(key="biology/content")
    assert (
        client.get_object(
            Bucket=MOCK_BUCKET_NAME, Key="biology/content/resources/biology.md"
        )
        is not None
    )
    delete_s3_objects(key="biology/content", as_filter=True)
    with pytest.raises(client.exceptions.NoSuchKey):
        client.get_object(
            Bucket=MOCK_BUCKET_NAME, Key="biology/content/resources/biology.md"
        )


@pytest.mark.parametrize("update_transcript_return_value", [True, False])
@pytest.mark.parametrize("is_ocw", [True, False])
@pytest.mark.parametrize(
    "initial_status", [VideoStatus.SUBMITTED_FOR_TRANSCRIPTION, VideoStatus.COMPLETE]
)
@pytest.mark.parametrize(
    "other_incomplete_video", [True, False]
)  # pylint: disable=too-many-arguments
def test_update_transcripts_for_video(
    settings,
    mocker,
    update_transcript_return_value,
    is_ocw,
    initial_status,
    other_incomplete_video,
):
    """Test update_transcripts_for_video"""
    mocker.patch("videos.tasks.is_ocw_site", return_value=is_ocw)
    mocker.patch("websites.api.is_ocw_site", return_value=is_ocw)

    transcripts_notification_mock = mocker.patch(
        "videos.tasks.mail_transcripts_complete_notification"
    )

    videofile = VideoFileFactory.create(
        destination=DESTINATION_YOUTUBE, destination_id="expected_id"
    )
    video = videofile.video
    video.pdf_transcript_file = f"{video.website.s3_path}/pdf_transcript"
    video.webvtt_transcript_file = f"{video.website.s3_path}/webvtt_transcript"
    video.status = initial_status
    video.save()

    resource = WebsiteContentFactory.create(website=video.website, metadata={})
    metadata = resource.metadata

    set_nested_dicts(metadata, settings.FIELD_RESOURCETYPE, RESOURCE_TYPE_VIDEO)
    set_nested_dicts(metadata, settings.YT_FIELD_ID, "expected_id")
    set_nested_dicts(metadata, settings.YT_FIELD_CAPTIONS, None)
    set_nested_dicts(metadata, settings.YT_FIELD_TRANSCRIPT, None)

    resource.save()

    if other_incomplete_video:
        other_resource = WebsiteContentFactory.create(
            website=video.website, metadata={}
        )
        metadata = other_resource.metadata
        set_nested_dicts(metadata, settings.FIELD_RESOURCETYPE, RESOURCE_TYPE_VIDEO)
        set_nested_dicts(metadata, settings.YT_FIELD_CAPTIONS, None)
        other_resource.save()

    update_transcript_mock = mocker.patch(
        "videos.tasks.threeplay_api.update_transcripts_for_video",
        return_value=update_transcript_return_value,
    )

    update_transcripts_for_video(video.id)
    update_transcript_mock.assert_called_with(video)

    resource.refresh_from_db()

    if update_transcript_return_value and is_ocw:
        assert (
            get_dict_field(resource.metadata, settings.YT_FIELD_CAPTIONS)
            == f"/{video.website.url_path}/webvtt_transcript"
        )
        assert (
            get_dict_field(resource.metadata, settings.YT_FIELD_TRANSCRIPT)
            == f"/{video.website.url_path}/pdf_transcript"
        )

        if initial_status == VideoStatus.SUBMITTED_FOR_TRANSCRIPTION and (
            not other_incomplete_video
        ):
            transcripts_notification_mock.assert_called_once()
        else:
            transcripts_notification_mock.assert_not_called()

    else:
        assert get_dict_field(resource.metadata, settings.YT_FIELD_CAPTIONS) is None
        assert get_dict_field(resource.metadata, settings.YT_FIELD_TRANSCRIPT) is None


def test_update_transcripts_for_updated_videos(mocker):
    """Test update_transcripts_for_updated_videos"""

    video_file = VideoFileFactory.create(
        destination=DESTINATION_YOUTUBE, destination_id="reference_id"
    )

    updated_files_mock = mocker.patch(
        "videos.tasks.threeplay_api.threeplay_updated_media_file_request",
        return_value=updated_transctipts_reponse(),
    )
    update_transcript_mock = mocker.patch(
        "videos.tasks.update_transcripts_for_video", return_value=True
    )
    remove_tags_mock = mocker.patch("videos.tasks.threeplay_api.threeplay_remove_tags")

    update_transcripts_for_updated_videos()

    updated_files_mock.assert_called_once()
    update_transcript_mock.assert_called_once_with(video_file.video.id)
    remove_tags_mock.assert_called_once_with(6737396)


@pytest.mark.parametrize(
    "caption_exists, transcript_exists",
    [
        [True, False],
        [False, True],
    ],
)
def test_update_transcripts_for_video_no_3play(
    mocker, caption_exists, transcript_exists
):
    """if there are caption/transcript resources, avoid calling 3play"""
    mocker.patch("videos.tasks.is_ocw_site", return_value=True)

    videofile = VideoFileFactory.create(
        destination=DESTINATION_YOUTUBE, destination_id="expected_id"
    )
    video = videofile.video
    resource = WebsiteContentFactory.create(website=video.website, metadata={})
    metadata = resource.metadata
    base_path = f"{resource.website.s3_path}/{resource.filename}"

    if caption_exists:
        WebsiteContentFactory.create(
            website=video.website,
            filename=f"{resource.filename}_captions",
            file=f"{base_path}_captions.vtt",
        )

    if transcript_exists:
        WebsiteContentFactory.create(
            website=video.website,
            filename=f"{resource.filename}_transcript",
            file=f"{base_path}_transcript.pdf",
        )

    set_dict_field(metadata, settings.FIELD_RESOURCETYPE, RESOURCE_TYPE_VIDEO)
    set_dict_field(metadata, settings.YT_FIELD_ID, "expected_id")
    set_dict_field(
        metadata,
        settings.YT_FIELD_CAPTIONS,
        (f"{base_path}_captions.vtt" if caption_exists else None),
    )
    set_dict_field(
        metadata,
        settings.YT_FIELD_TRANSCRIPT,
        (f"{base_path}_transcript.pdf" if transcript_exists else None),
    )
    resource.save()

    if caption_exists:
        assert video.caption_transcript_resources()[0] is not None
    if transcript_exists:
        assert video.caption_transcript_resources()[1] is not None

    mock_3play = mocker.patch("videos.tasks.threeplay_api.update_transcripts_for_video")

    update_transcripts_for_video(video.id)
    resource.refresh_from_db()

    mock_3play.assert_not_called()

    assert get_dict_field(resource.metadata, settings.YT_FIELD_CAPTIONS) == (
        f"/{video.website.url_path}/{resource.filename}_captions.vtt"
        if caption_exists
        else None
    )
    assert get_dict_field(resource.metadata, settings.YT_FIELD_TRANSCRIPT) == (
        f"/{video.website.url_path}/{resource.filename}_transcript.pdf"
        if transcript_exists
        else None
    )


def test_attempt_to_update_missing_transcripts(mocker):
    """Test attempt_to_update_missing_transcripts"""

    videofile = VideoFileFactory.create(
        destination=DESTINATION_YOUTUBE, destination_id="reference_id"
    )
    website = videofile.video.website
    website.publish_date = datetime.now(pytz.timezone("America/New_York"))
    website.save()

    update_transcript_mock = mocker.patch("videos.tasks.update_transcripts_for_video")

    attempt_to_update_missing_transcripts()

    update_transcript_mock.delay.assert_called_once_with(videofile.video.id)


def test_update_transcripts_for_website(mocker):
    """test update_transcripts_for_website"""
    website = WebsiteFactory.create()
    videos = VideoFactory.create_batch(4, website=website)
    update_video_transcript = mocker.patch("videos.tasks.update_transcripts_for_video")

    update_transcripts_for_website(website)

    for video in videos:
        update_video_transcript.assert_any_call(video.id)


def test_mail_transcripts_complete_notification(settings, mocker):
    """mail_transcripts_complete_notification should send correct email to correct users"""
    website = WebsiteFactory.create()
    users = UserFactory.create_batch(4)
    for user in users[:2]:
        user.groups.add(website.admin_group)
    for user in users[2:]:
        user.groups.add(website.editor_group)

    mock_get_message_sender = mocker.patch("videos.tasks.get_message_sender")
    mock_sender = mock_get_message_sender.return_value.__enter__.return_value

    mail_transcripts_complete_notification(website)

    mock_get_message_sender.assert_called_once_with(VideoTranscriptingCompleteMessage)
    assert mock_sender.build_and_send_message.call_count == len(users) + 1
    for user in users:
        mock_sender.build_and_send_message.assert_any_call(
            user,
            {
                "site": {
                    "title": website.title,
                    "url": urljoin(settings.SITE_BASE_URL, f"/sites/{website.name}"),
                },
            },
        )
