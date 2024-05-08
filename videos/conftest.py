"""Common test vars for videos"""
import pytest

TEST_VIDEOS_WEBHOOK_PATH = "./test_videos_webhook"


class MockHttpErrorResponse:
    """
    Mock googleapiclient.HttpError response
    """

    def __init__(self, status, reason="mock reason"):
        self.status = status
        self.reason = reason


@pytest.fixture(autouse=True)
def valid_settings(settings):  # noqa: PT004
    """Valid settings for video processing"""  # noqa: D401
    settings.AWS_ACCOUNT_ID = "account-id"
    settings.AWS_REGION = "us-west-1"
    settings.AWS_ROLE_NAME = "mediaconvert-role"
    settings.AWS_STORAGE_BUCKET_NAME = "test_bucket"
    settings.DRIVE_S3_UPLOAD_PREFIX = "test-upload"
    settings.VIDEO_S3_TRANSCODE_PREFIX = "test-transcode"


@pytest.fixture(autouse=True)
def youtube_settings(settings, mocker):  # noqa: PT004
    """Populate required youtube settings with dummy values"""
    settings.YT_CLIENT_ID = "testvalue"
    settings.YT_CLIENT_SECRET = "testvalue"  # pragma: allowlist secret  # noqa: S105
    settings.YT_PROJECT_ID = "testvalue"
    settings.YT_ACCESS_TOKEN = "testvalue"  # noqa: S105
    settings.YT_REFRESH_TOKEN = "testvalue"  # noqa: S105
    mocker.patch("videos.youtube.Credentials")


@pytest.fixture(autouse=True)
def mock_smart_open_reader(mocker):  # noqa: PT004
    """Mock the smartopen s3 Reader"""
    mocker.patch("videos.youtube.Reader")
