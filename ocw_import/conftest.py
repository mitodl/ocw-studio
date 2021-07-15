"""Test config for ocw_import app"""
import glob
from os.path import isfile

import pytest

from main.s3_utils import get_s3_resource
from websites.factories import WebsiteFactory


TEST_OCW2HUGO_PREFIX = "output/"
TEST_OCW2HUGO_PATH = f"./test_hugo2ocw/{TEST_OCW2HUGO_PREFIX}"
TEST_OCW2HUGO_FILES = [
    f for f in glob.glob(TEST_OCW2HUGO_PATH + "**/*", recursive=True) if isfile(f)
]
MOCK_BUCKET_NAME = "testbucket"


def setup_s3(settings):
    """
    Set up the fake s3 data
    """
    # Fake the settings
    settings.AWS_ACCESS_KEY_ID = "abc"
    settings.AWS_SECRET_ACCESS_KEY = "abc"
    # Create our fake bucket
    conn = get_s3_resource()
    conn.create_bucket(Bucket=MOCK_BUCKET_NAME)

    # Add data to the fake bucket
    test_bucket = conn.Bucket(name=MOCK_BUCKET_NAME)
    for file in TEST_OCW2HUGO_FILES:
        file_key = file.replace("./test_hugo2ocw/", "")
        with open(file, "r") as f:
            test_bucket.put_object(Key=file_key, Body=f.read())


@pytest.fixture(autouse=True)
def root_website():
    """Create the ocw-www website"""
    yield WebsiteFactory.create(name="ocw-www")
