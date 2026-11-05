"""Tests for the unpublish_sites management command"""  # noqa: INP001

import pytest
from django.core.management import call_command

from content_sync.constants import VERSION_LIVE
from users.factories import UserFactory
from websites.constants import PUBLISH_STATUS_NOT_STARTED
from websites.factories import WebsiteFactory, WebsiteStarterFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("is_default_theme_site", [True, False])
def test_unpublish_sites_pauses_live_pipelines(mocker, settings, is_default_theme_site):
    """unpublish_sites should pause the live pipelines of a site, including those of its extra themes"""
    settings.CONTENT_SYNC_PIPELINE_BACKEND = "concourse"
    settings.OCW_DEFAULT_COURSE_THEME = "ocw-course-v2"
    settings.OCW_EXTRA_COURSE_THEMES = ["ocw-course-v3"]
    mock_get_site_pipeline = mocker.patch("content_sync.api.get_site_pipeline")
    mock_get_removal_pipeline = mocker.patch(
        "content_sync.api.get_unpublished_removal_pipeline"
    )
    mocker.patch(
        "websites.management.commands.unpublish_sites.remove_website_in_root_website"
    )
    mock_update_mass_builds = mocker.patch(
        "websites.management.commands.unpublish_sites.update_mass_build_pipelines_on_publish"
    )
    user = UserFactory.create()
    website = WebsiteFactory.create(
        published=True,
        starter=WebsiteStarterFactory.create(slug="ocw-course-v2")
        if is_default_theme_site
        else WebsiteStarterFactory.create(),
    )

    call_command("unpublish_sites", filter=website.name, user=user.email)

    website.refresh_from_db()
    assert website.unpublish_status == PUBLISH_STATUS_NOT_STARTED
    paused = [
        call.args[0]
        for call in mock_get_site_pipeline.return_value.pause_pipeline.call_args_list
    ]
    assert paused == (
        [VERSION_LIVE, f"{VERSION_LIVE}-ocw-course-v3"]
        if is_default_theme_site
        else [VERSION_LIVE]
    )
    mock_update_mass_builds.delay.assert_called_once_with(
        version=VERSION_LIVE, website_pk=website.pk, both_versions=True
    )
    mock_get_removal_pipeline.return_value.trigger.assert_called_once_with()
