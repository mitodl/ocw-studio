""" Concourse-CI preview/publish pipeline generator"""
import os

from django.conf import settings
from fly import Fly

from content_sync.apis.github import get_repo_name
from content_sync.pipelines.base import BaseSyncPipeline
from websites.site_config_api import SiteConfig


class ConcourseGithubPipeline(BaseSyncPipeline):
    """
    Concourse-CI publishing pipeline, dependent on a Github backend
    """

    MANDATORY_SETTINGS = [
        "AWS_PREVIEW_BUCKET_NAME",
        "AWS_PUBLISH_BUCKET_NAME",
        "AWS_STORAGE_BUCKET_NAME",
        "CONCOURSE_URL",
        "CONCOURSE_USERNAME",
        "CONCOURSE_PASSWORD",
        "GIT_BRANCH_PREVIEW",
        "GIT_BRANCH_RELEASE",
        "GIT_DOMAIN",
        "GIT_ORGANIZATION",
        "GITHUB_WEBHOOK_BRANCH",
    ]

    def upsert_website_pipeline(self):
        """
        Create or update a concourse pipeline for the given Website
        """
        site_config = SiteConfig(self.website.starter.config)
        site_url = f"{site_config.root_url_path}/{self.website.name}".strip("/")
        base_url = (
            "" if self.website.starter.slug == settings.ROOT_WEBSITE_SLUG else site_url
        )
        purge_url = "purge_all" if not base_url else f"purge/{site_url}"

        fly = Fly(concourse_url=settings.CONCOURSE_URL)
        fly.login(
            username=settings.CONCOURSE_USERNAME,
            password=settings.CONCOURSE_PASSWORD,
            team_name=settings.CONCOURSE_TEAM,
        )
        for branch in [settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_RELEASE]:
            if branch == settings.GIT_BRANCH_PREVIEW:
                version = "draft"
                destination_bucket = settings.AWS_PREVIEW_BUCKET_NAME
            else:
                version = "live"
                destination_bucket = settings.AWS_PUBLISH_BUCKET_NAME

            fly.run(
                "set-pipeline",
                "-p",
                version,
                "--team",
                settings.CONCOURSE_TEAM,
                "-c",
                os.path.join(
                    os.path.dirname(__file__), "definitions/concourse/site-pipeline.yml"
                ),
                "--instance-var",
                f"site={self.website.name}",
                "-v",
                f"git-domain={settings.GIT_DOMAIN}",
                "-v",
                f"github-org={settings.GIT_ORGANIZATION}",
                "-v",
                f"ocw-bucket={destination_bucket}",
                "-v",
                f"ocw-hugo-projects-branch={settings.GITHUB_WEBHOOK_BRANCH}",
                "-v",
                f"ocw-studio-url={os.environ.get('OCW_STUDIO_BASE_URL')}",
                "-v",
                f"ocw-studio-bucket={settings.AWS_STORAGE_BUCKET_NAME}",
                "-v",
                f"ocw-site-repo={get_repo_name(self.website)}",
                "-v",
                f"ocw-site-repo-branch={branch}",
                "-v",
                f"config-slug={self.website.starter.slug}",
                "-v",
                f"base-url={base_url}",
                "-v",
                f"site-url={site_url}",
                "-v",
                f"purge-url={purge_url}",
                "-n",
            )
            fly.run(
                "unpause-pipeline",
                "--team",
                settings.CONCOURSE_TEAM,
                "-p",
                f"{version}/site:{self.website.name}",
            )
