"""Test config for websites app"""
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group

from users.factories import UserFactory
from websites import constants
from websites.factories import WebsiteFactory, WebsiteContentFactory


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
        global_author=global_author,
        site_admin=site_admin,
        site_editor=site_editor,
        websites=websites,
        owner_content=owner_content,
        editor_content=editor_content,
    )
