""" Test config for websites """
import glob
from os.path import isfile
from types import SimpleNamespace

import boto3
import pytest

MOCK_BUCKET_NAME = "testbucket"
TEST_OCW2HUGO_PREFIX = "output/"
TEST_OCW2HUGO_PATH = f"./test_hugo2ocw/{TEST_OCW2HUGO_PREFIX}"
TEST_OCW2HUGO_FILES = [
    f for f in glob.glob(TEST_OCW2HUGO_PATH + "**/*", recursive=True) if isfile(f)
]


@pytest.fixture()
def mocked_celery(mocker):
    """Mock object that patches certain celery functions"""
    exception_class = TabError
    replace_mock = mocker.patch(
        "celery.app.task.Task.replace", autospec=True, side_effect=exception_class
    )
    group_mock = mocker.patch("celery.group", autospec=True)
    chain_mock = mocker.patch("celery.chain", autospec=True)

    yield SimpleNamespace(
        replace=replace_mock,
        group=group_mock,
        chain=chain_mock,
        replace_exception_class=exception_class,
    )


def setup_s3(settings):
    """
    Set up the fake s3 data
    """
    # Fake the settings
    settings.AWS_ACCESS_KEY_ID = "abc"
    settings.AWS_SECRET_ACCESS_KEY = "abc"
    # Create our fake bucket
    conn = boto3.resource(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    conn.create_bucket(Bucket=MOCK_BUCKET_NAME)

    # Add data to the fake bucket
    test_bucket = conn.Bucket(name=MOCK_BUCKET_NAME)
    for file in TEST_OCW2HUGO_FILES:
        file_key = file.replace("./test_hugo2ocw/", "")
        with open(file, "r") as f:
            test_bucket.put_object(Key=file_key, Body=f.read())
