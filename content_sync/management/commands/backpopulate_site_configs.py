""" Create site_config.json files for website repos """
from uuid import UUID

from django.conf import settings
from django.core.management import BaseCommand

from content_sync.apis.github import GithubApiWrapper
from websites.api import fetch_website
from websites.models import Website


def is_valid_uuid(uuid_str: str) -> bool:
    """Determine if a string is a valid uuid"""
    try:
        UUID(uuid_str)
        return True
    except ValueError:
        return False


class Command(BaseCommand):
    """ Creates a site_config.json file for a specific or every website repo """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "--website",
            dest="website",
            help="The uuid, name, or title of a specific Website that should be synced.",
            required=False,
        )

    def add_site_config(self, website: Website) -> GithubApiWrapper:
        """ Add a site config file to a website """
        git_api = GithubApiWrapper(website, site_config=website.starter.config)
        git_api.get_repo()
        self.stdout.write(f"Creating site config file for '{website.title}'...")
        response = git_api.upsert_site_config_file(commit_msg="Add site config file")
        for branch in [settings.GIT_BRANCH_PREVIEW, settings.GIT_BRANCH_RELEASE]:
            git_api.repo.merge(
                branch, response["commit"].sha, f"Merge site config file to {branch}"
            )
        return git_api

    def handle(self, *args, **options):
        website = (
            fetch_website(options["website"])
            if options["website"]
            else Website.objects.first()
        )
        git_api = self.add_site_config(website)
        if not options["website"]:
            # Iterate over all other existing repos
            for repo in git_api.org.get_repos(sort="full_name"):
                uid = repo.name.split("_")[-1]
                if is_valid_uuid(uid):
                    repo_website = Website.objects.filter(uuid=uid).first()
                    if repo_website and repo_website.uuid != website.uuid:
                        self.add_site_config(repo_website)
