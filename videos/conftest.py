"""Common test vars for videos"""

import pytest

from main.s3_utils import get_boto3_resource

MOCK_BUCKET_NAME = "testbucket"
TEST_VIDEOS_WEBHOOK_PATH = "./test_videos_webhook"


class MockHttpErrorResponse:
    """
    Mock googleapiclient.HttpError response
    """

    def __init__(self, status, reason="mock reason"):
        self.status = status
        self.reason = reason


def setup_s3(settings, test_files=None):
    """
    Set up fake s3 data
    """
    # Fake the settings
    settings.ENVIRONMENT = "test"
    settings.AWS_ACCESS_KEY_ID = "abc"
    settings.AWS_SECRET_ACCESS_KEY = "abc"  # noqa: S105
    # Create our fake bucket
    conn = get_boto3_resource("s3")
    conn.create_bucket(Bucket=MOCK_BUCKET_NAME)

    # Add data to the fake bucket
    test_bucket = conn.Bucket(name=MOCK_BUCKET_NAME)
    test_bucket.objects.all().delete()
    if test_files:
        for key, content in test_files.items():
            test_bucket.put_object(Key=key, Body=content)


@pytest.fixture(autouse=True)
def valid_settings(settings):
    """Valid settings for video processing"""  # noqa: D401
    settings.AWS_ACCOUNT_ID = "account-id"
    settings.AWS_REGION = "us-west-1"
    settings.AWS_ROLE_NAME = "mediaconvert-role"
    settings.AWS_STORAGE_BUCKET_NAME = "test_bucket"
    settings.DRIVE_S3_UPLOAD_PREFIX = "test-upload"
    settings.VIDEO_S3_TRANSCODE_PREFIX = "test-transcode"
    settings.VIDEO_TRANSCODE_QUEUE = "test-queue"
    settings.TRANSCODE_JOB_TEMPLATE = "./videos/config/mediaconvert.json"
    settings.POST_TRANSCODE_ACTIONS = ["videos.api.update_video_job"]


@pytest.fixture(autouse=True)
def youtube_settings(settings, mocker):
    """Populate required youtube settings with dummy values"""
    settings.YT_CLIENT_ID = "testvalue"
    settings.YT_CLIENT_SECRET = "testvalue"  # pragma: allowlist secret  # noqa: S105
    settings.YT_PROJECT_ID = "testvalue"
    settings.YT_ACCESS_TOKEN = "testvalue"  # noqa: S105
    settings.YT_REFRESH_TOKEN = "testvalue"  # noqa: S105
    mocker.patch("videos.youtube.Credentials")


@pytest.fixture(autouse=True)
def mock_smart_open_reader(mocker):
    """Mock the smartopen s3 Reader"""
    mocker.patch("videos.youtube.Reader")
