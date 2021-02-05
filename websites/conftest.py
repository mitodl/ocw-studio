""" Test config for websites """
import glob
from os.path import isfile
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group

from main.s3_utils import get_s3_resource
from users.factories import UserFactory
from websites import constants
from websites.factories import WebsiteFactory, WebsiteContentFactory
from websites.models import WebsiteStarter

MOCK_BUCKET_NAME = "testbucket"
TEST_OCW2HUGO_PREFIX = "output/"
TEST_OCW2HUGO_PATH = f"./test_hugo2ocw/{TEST_OCW2HUGO_PREFIX}"
TEST_OCW2HUGO_FILES = [
    f for f in glob.glob(TEST_OCW2HUGO_PATH + "**/*", recursive=True) if isfile(f)
]


@pytest.fixture()
@pytest.mark.django_db
def course_starter():
    """Returns the 'course'-type WebsiteStarter that is seeded in a data migration"""
    return WebsiteStarter.objects.get(slug=constants.COURSE_STARTER_SLUG)


@pytest.fixture()
def permission_groups():
    """Set up groups, users and websites for permission testing"""
    (
        global_admin,
        global_author,
        site_owner,
        site_admin,
        site_editor,
    ) = UserFactory.create_batch(5)
    websites = WebsiteFactory.create_batch(2, owner=site_owner)
    global_admin.groups.add(Group.objects.get(name=constants.GLOBAL_ADMIN))
    global_author.groups.add(Group.objects.get(name=constants.GLOBAL_AUTHOR))
    site_admin.groups.add(websites[0].admin_group)
    site_editor.groups.add(websites[0].editor_group)

    website = websites[0]
    owner_content = WebsiteContentFactory.create(website=website, owner=website.owner)
    editor_content = WebsiteContentFactory.create(website=website, owner=site_editor)

    yield SimpleNamespace(
        global_admin=global_admin,
        global_editor=global_author,
        site_admin=site_admin,
        site_editor=site_editor,
        websites=websites,
        owner_content=owner_content,
        editor_content=editor_content,
    )


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
