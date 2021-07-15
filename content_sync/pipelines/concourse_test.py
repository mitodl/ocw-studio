""" concourse tests """
import os

import pytest
from django.core.exceptions import ImproperlyConfigured

from content_sync.apis.github import get_repo_name
from content_sync.pipelines.concourse import ConcourseGithubPipeline
from websites.factories import WebsiteFactory, WebsiteStarterFactory


pytestmark = pytest.mark.django_db
# pylint:disable=redefined-outer-name


def test_upsert_website_pipeline_missing_settings(settings, mock_fly):
    """An exception should be raised if required settings are missing"""
    settings.AWS_PREVIEW_BUCKET_NAME = None
    website = WebsiteFactory.create()
    with pytest.raises(ImproperlyConfigured):
        ConcourseGithubPipeline(website)
    mock_fly.login.assert_not_called()


def test_upsert_website_pipeline_homepage(settings, mock_fly):
    """The correct fly calls/args should be made for a draft 'home page' website"""
    root_slug = "ocw-www"
    settings.ROOT_WEBSITE_SLUG = root_slug
    starter = WebsiteStarterFactory.create(slug=root_slug)
    starter.config["root-url-path"] = ""
    website = WebsiteFactory.create(starter=starter)
    pipeline = ConcourseGithubPipeline(website)
    pipeline.upsert_website_pipeline()
    mock_fly.return_value.login.assert_called_once_with(
        username=settings.CONCOURSE_USERNAME,
        password=settings.CONCOURSE_PASSWORD,
        team_name=settings.CONCOURSE_TEAM,
    )
    mock_fly.return_value.run.assert_any_call(
        "set-pipeline",
        "-p",
        "draft",
        "--team",
        settings.CONCOURSE_TEAM,
        "-c",
        os.path.join(
            os.path.dirname(__file__), "definitions/concourse/site-pipeline.yml"
        ),
        "--instance-var",
        f"site={website.name}",
        "-v",
        f"git-domain={settings.GIT_DOMAIN}",
        "-v",
        f"github-org={settings.GIT_ORGANIZATION}",
        "-v",
        f"ocw-bucket={settings.AWS_PREVIEW_BUCKET_NAME}",
        "-v",
        f"ocw-hugo-projects-branch={settings.GITHUB_WEBHOOK_BRANCH}",
        "-v",
        "ocw-studio-url=http://test.edu",
        "-v",
        f"ocw-studio-bucket={settings.AWS_STORAGE_BUCKET_NAME}",
        "-v",
        f"ocw-site-repo={get_repo_name(website)}",
        "-v",
        "ocw-site-repo-branch=preview",
        "-v",
        f"config-slug={starter.slug}",
        "-v",
        "base-url=",
        "-v",
        f"site-url={website.name}",
        "-v",
        "purge-url=purge_all",
        "-n",
    )


def test_upsert_website_pipeline_course(settings, mock_fly):
    """The correct fly calls/args should be made for a live course website"""
    website = WebsiteFactory.create()
    website.starter.config["root-url-path"] = "courses"
    pipeline = ConcourseGithubPipeline(website)
    pipeline.upsert_website_pipeline()
    mock_fly.return_value.run.assert_any_call(
        "set-pipeline",
        "-p",
        "live",
        "--team",
        settings.CONCOURSE_TEAM,
        "-c",
        os.path.join(
            os.path.dirname(__file__), "definitions/concourse/site-pipeline.yml"
        ),
        "--instance-var",
        f"site={website.name}",
        "-v",
        f"git-domain={settings.GIT_DOMAIN}",
        "-v",
        f"github-org={settings.GIT_ORGANIZATION}",
        "-v",
        f"ocw-bucket={settings.AWS_PUBLISH_BUCKET_NAME}",
        "-v",
        f"ocw-hugo-projects-branch={settings.GITHUB_WEBHOOK_BRANCH}",
        "-v",
        "ocw-studio-url=http://test.edu",
        "-v",
        f"ocw-studio-bucket={settings.AWS_STORAGE_BUCKET_NAME}",
        "-v",
        f"ocw-site-repo={get_repo_name(website)}",
        "-v",
        "ocw-site-repo-branch=release",
        "-v",
        f"config-slug={website.starter.slug}",
        "-v",
        f"base-url=courses/{website.name}",
        "-v",
        f"site-url=courses/{website.name}",
        "-v",
        f"purge-url=purge/courses/{website.name}",
        "-n",
    )
