""" Common test vars for videos"""
import pytest


TEST_VIDEOS_WEBHOOK_PATH = "./test_videos_webhook"


@pytest.fixture(autouse=True)
def valid_settings(settings):
    """Valid settings for video processing"""
    settings.AWS_ACCOUNT_ID = "account-id"
    settings.AWS_REGION = "us-west-1"
    settings.AWS_ROLE_NAME = "mediaconvert-role"
    settings.AWS_STORAGE_BUCKET_NAME = "test_bucket"
    settings.DRIVE_S3_UPLOAD_PREFIX = "test-upload"
    settings.VIDEO_S3_TRANSCODE_PREFIX = "test-transcode"
