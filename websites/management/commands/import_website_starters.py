"""Import WebsiteStarter objects from ocw-studio.yaml files in a Github repo"""  # noqa: E501 INP001
from urllib.parse import urlparse

from django.conf import settings
from django.core.management import BaseCommand
from github import Github

from content_sync.apis.github import find_files_recursive, sync_starter_configs


class Command(BaseCommand):
    """Import WebsiteStarter objects from ocw-studio.yaml files in a Github repo"""

    help = __doc__  # noqa: A003

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

    def handle(self, *args, **options):  # noqa: ARG002
        git_url = options["git_url"]
        commit = options["commit"]

        repo_path = urlparse(git_url).path.lstrip("/")
        org_name, repo_name = repo_path.split("/", 1)
        git = Github()
        org = git.get_organization(org_name)
        repo = org.get_repo(repo_name)
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
                repo_url=git_url, config_files=config_files, commit=commit
            )
            self.stdout.write("Successfully updated WebsiteStarter objects")
        else:
            self.stdout.write("No ocw-studio.yaml files found in the given repository")
