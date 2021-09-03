"""Test config for ocw_import app"""
import glob
from os.path import isfile
from shutil import copytree, rmtree

import pytest

from main.s3_utils import get_s3_resource
from websites.factories import WebsiteFactory


MOCK_BUCKET_NAME = "testbucket"
TEST_OCW2HUGO_PREFIX = ""


def get_ocw2hugo_path(path):
    """ get the path to ocw-to-hugo test data """
    return f"{path}/{TEST_OCW2HUGO_PREFIX}"


def get_ocw2hugo_files(path):
    """ get the files from an ocw-to-hugo test data directory """
    return [
        f
        for f in glob.glob(get_ocw2hugo_path(path) + "**/*", recursive=True)
        if isfile(f)
    ]


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
    test_bucket.objects.all().delete()
    for file in get_ocw2hugo_files("./test_ocw2hugo"):
        file_key = file.replace("./test_ocw2hugo/", "")
        with open(file, "r") as f:
            test_bucket.put_object(Key=file_key, Body=f.read())


def setup_s3_tmpdir(settings, tmpdir, courses=None):
    """
    Set up the fake s3 data
    """
    # Fake the settings
    settings.AWS_ACCESS_KEY_ID = "abc"
    settings.AWS_SECRET_ACCESS_KEY = "abc"
    # Create our fake bucket
    conn = get_s3_resource()
    conn.create_bucket(Bucket=MOCK_BUCKET_NAME)
    # Copy test data to tmpdir
    rmtree(tmpdir)
    if courses is not None:
        for course in courses:
            copytree(f"./test_ocw2hugo/{course}/", f"{tmpdir}/{course}/")
    else:
        copytree("./test_ocw2hugo/", f"{tmpdir}/")

    # Add data to the fake bucket
    test_bucket = conn.Bucket(name=MOCK_BUCKET_NAME)
    test_bucket.objects.all().delete()
    for file in get_ocw2hugo_files(tmpdir):
        file_key = file.replace(f"{tmpdir}/", "")
        with open(file, "r") as f:
            test_bucket.put_object(Key=file_key, Body=f.read())


@pytest.fixture(autouse=True)
def root_website():
    """Create the ocw-www website"""
    yield WebsiteFactory.create(name="ocw-www")
