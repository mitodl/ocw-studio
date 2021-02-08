""" Backpopulate website groups and permissions"""
from django.core.management import BaseCommand

from main.utils import now_in_utc
from websites.models import Website
from websites.permissions import create_global_groups, create_website_groups


class Command(BaseCommand):
    """ Backpopulate website groups and permissions """

    help = "Backpopulate website groups and permissions"

    def handle(self, *args, **options):

        self.stdout.write(f"Creating website permission groups")
        start = now_in_utc()

        # Redo global grpups too in case permissions changed
        created, updated = create_global_groups()
        self.stdout.write(
            f"Global groups: created {created} groups, updated {updated} groups"
        )

        for website in Website.objects.iterator():
            created, updated, owner_updated = create_website_groups(website)
            self.stdout.write(
                f"{website.name} groups: created {created}, updated {updated}, owner updated: {str(owner_updated)}"
            )

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Creation of website permission groups finished, took {} seconds".format(
                total_seconds
            )
        )
