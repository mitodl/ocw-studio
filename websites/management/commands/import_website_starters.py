"""Import WebsiteStarter objects from ocw-studio.yaml files in a Github repo"""  # noqa: INP001

from urllib.parse import urlparse

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from github import Github

from content_sync.apis.github import (
    find_files_recursive,
    get_newest_release_tag,
    sync_starter_configs,
)
from content_sync.utils import get_hugo_tag_regex


class Command(BaseCommand):
    """Import WebsiteStarter objects from ocw-studio.yaml files in a Github repo"""

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "git_url",
            help="The URL to the Github repo",
        )
        parser.add_argument(
            "-c",
            "--commit",
            dest="commit",
            default=None,
            help="If specified, use a specific commit hash",
        )
        parser.add_argument(
            "-t",
            "--tag",
            dest="tag",
            default=None,
            help=(
                "The release tag to import from when OCW_HUGO_TAG_RELEASES is on, "
                "which has to be the newest release tag. Defaults to that tag."
            ),
        )

    def handle(self, *args, **options):  # noqa: ARG002
        git_url = options["git_url"]
        commit = options["commit"]
        tag = options["tag"]

        repo_path = urlparse(git_url).path.lstrip("/")
        org_name, repo_name = repo_path.split("/", 1)
        git = Github(timeout=settings.GITHUB_TIMEOUT)
        org = git.get_organization(org_name)
        repo = org.get_repo(repo_name)
        tag_regex = get_hugo_tag_regex(settings.GITHUB_WEBHOOK_BRANCH)
        if tag_regex:
            # The repo has no release branch, so read the newest release tag
            tag = tag or get_newest_release_tag(repo, tag_regex)
            if not tag:
                msg = (
                    "No release tag matches the pattern, so there is nothing to import"
                )
                raise CommandError(msg)
            commit = repo.get_commit(tag).sha
        config_files = find_files_recursive(
            repo=repo,
            path="",
            file_name=settings.OCW_STUDIO_SITE_CONFIG_FILE,
            commit=commit,
        )
        num_config_files = len(config_files)
        if num_config_files > 0:
            self.stdout.write(
                f"Creating or updating WebsiteStarter objects for {num_config_files} config files: {config_files}"  # noqa: E501
            )
            sync_starter_configs(
                repo_url=git_url, config_files=config_files, commit=commit, tag=tag
            )
            self.stdout.write("Successfully updated WebsiteStarter objects")
        else:
            self.stdout.write("No ocw-studio.yaml files found in the given repository")
