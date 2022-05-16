"""Test config for websites app"""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from django.contrib.auth.models import Group

from users.factories import UserFactory
from websites import constants
from websites.constants import CONTENT_TYPE_METADATA
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.permissions import create_global_groups


# pylint:disable=redefined-outer-name

FACTORY_SITE_CONFIG_PATH = "localdev/configs/basic-site-config.yml"
SCHEMA_RESOURCES_DIR = "localdev/configs/"
SCHEMA_CONFIG_FILE = "ocw-course-site-config.yml"


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
    websites = WebsiteFactory.create_batch(2, owner=site_owner, with_url_path=True)
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


@pytest.fixture()
def global_admin_user():
    """Returns a user with global admin permissions"""
    create_global_groups()
    global_admin_user = UserFactory.create()
    global_admin_user.groups.add(Group.objects.get(name=constants.GLOBAL_ADMIN))
    return global_admin_user


@pytest.fixture()
def basic_site_config(settings):
    """Returns an example site config"""
    return yaml.load(
        (Path(settings.BASE_DIR) / FACTORY_SITE_CONFIG_PATH).read_text(),
        Loader=yaml.SafeLoader,
    )


@pytest.fixture()
def site_config_yml(settings):
    """Fixture that returns the contents of the example site config YAML file in the resource directory"""
    with open(
        os.path.join(settings.BASE_DIR, SCHEMA_RESOURCES_DIR, SCHEMA_CONFIG_FILE)
    ) as f:
        return f.read().strip()


@pytest.fixture()
def parsed_site_config(site_config_yml):
    """Fixture that returns the parsed contents of the example site config YAML file in the resource directory"""
    return yaml.load(site_config_yml, Loader=yaml.SafeLoader)


@pytest.fixture()
def site_config_repeatable_only(basic_site_config):
    """Returns an example site config with a repeatable config item as the only item in 'collections'"""
    site_config = basic_site_config.copy()
    config_item = site_config["collections"][0]
    assert (
        "folder" in config_item
    ), "Expected collections.0 to be a repeatable config item"
    return {**site_config, "collections": [config_item]}


@pytest.fixture()
def site_config_singleton_only(basic_site_config):
    """Returns an example site config with a singleton config item as the only item in 'collections'"""
    site_config = basic_site_config.copy()
    files_config_item = site_config["collections"][2]
    file_config_item = files_config_item.get("files", [None])[0]
    assert (
        "file" in file_config_item
    ), "Expected collections.2.files.0 to be a singleton config item"
    return {**site_config, "collections": [files_config_item]}


@pytest.fixture()
def ocw_site(parsed_site_config):
    """ OCW Course site with metadata"""
    website = WebsiteFactory.create(
        starter=WebsiteStarterFactory.create(config=parsed_site_config)
    )
    WebsiteContentFactory(type=CONTENT_TYPE_METADATA, website=website)
    return website
