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
        create_global_groups()

        for website in Website.objects.iterator():
            create_website_groups(website)

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(
            "Creation of website permission groups finished, took {} seconds".format(
                total_seconds
            )
        )
