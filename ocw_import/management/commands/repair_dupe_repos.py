""" Fix sites that have been assigned a new repo on every import """
from django.core.management import BaseCommand
from django.db import transaction
from github import GithubException
from mitol.common.utils.datetime import now_in_utc

from content_sync.api import get_sync_backend, get_sync_pipeline
from content_sync.models import ContentSyncState
from websites.models import Website


class Command(BaseCommand):
    """  Fix sites that have been assigned a new repo on every import"""

    help = __doc__

    def handle(self, *args, **options):
        self.stdout.write("Fixing repos for imported OCW sites")
        start = now_in_utc()
        errors = 0
        websites = (
            Website.objects.exclude(short_id__endswith="-2")
            .filter(source="ocw-import", short_id__regex=r".+\-\d{1,2}$")
            .order_by("name")
        )
        self.stdout.write(f"Repairing repos for {websites.count()} sites")
        for website in websites:
            try:
                with transaction.atomic():
                    short_id_secs = website.short_id.split("-")
                    base_repo, idx = ("-".join(short_id_secs[:-1]), short_id_secs[-1])
                    website.short_id = f"{base_repo}-2"
                    website.save()
                    ContentSyncState.objects.filter(content__website=website).update(
                        synced_checksum=None, data=None
                    )
                    backend = get_sync_backend(website)
                    backend.sync_all_content_to_backend()
                    get_sync_pipeline(website).upsert_pipeline()
                    for i in range(3, int(idx) + 1):
                        try:
                            backend.api.org.get_repo(f"{base_repo}-{i}").delete()
                        except GithubException as ge:
                            if ge.status != 404:
                                raise
            except Exception as exc:  # pylint:disable=broad-except
                self.stderr.write(
                    f"Error occurred repairing repo for {website.name}: {exc}"
                )
                errors += 1

        total_seconds = (now_in_utc() - start).total_seconds()
        if errors == 0:
            self.stdout.write(f"Repo repair finished, took {total_seconds} seconds")
        else:
            self.stderr.write(
                f"Repo repair finished with {errors} errors, took {total_seconds} seconds"
            )
