"""Update websites in the root website"""  # noqa: INP001

from django.conf import settings
from mitol.common.utils.datetime import now_in_utc

from content_sync.tasks import update_websites_in_root_website
from main.management.commands.filter import WebsiteFilterCommand


class Command(WebsiteFilterCommand):
    """Update website WebsiteContent objects in the root website denoted by settings.ROOT_WEBSITE_NAME"""  # noqa: E501

    help = __doc__

    def add_arguments(self, parser):
        super().add_arguments(parser)

    def handle(self, *args, **options):
        super().handle(*args, **options)

        root_website_name = settings.ROOT_WEBSITE_NAME
        self.stdout.write(f"Updating websites in the root website, {root_website_name}")

        start = now_in_utc()
        task = update_websites_in_root_website.delay()

        self.stdout.write(
            f"Started celery task {task} to update websites in the root website, {root_website_name}"  # noqa: E501
        )

        self.stdout.write("Waiting on task...")

        task.get()

        total_seconds = (now_in_utc() - start).total_seconds()
        self.stdout.write(f"Update finished, took {total_seconds} seconds")
