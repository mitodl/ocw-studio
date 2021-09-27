from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import Q

from gdrive_sync import api
from websites.models import Website


class Command(BaseCommand):
    """Creates a gdrive folder for video uploads for websites that don't already have one"""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-w",
            "--website",
            dest="website",
            default="",
            help="If specified, only process websites that have this short_id or name",
        )

    def handle(self, *args, **options):
        if settings.DRIVE_SHARED_ID and settings.DRIVE_SERVICE_ACCOUNT_CREDS:
            websites = Website.objects.filter(owner_id__isnull=False)
            website_filter = options["website"].lower()
            if website_filter:
                websites = websites.filter(
                    Q(name__icontains=website_filter)
                    | Q(short_id__icontains=website_filter)
                )

            self.stdout.write(
                self.style.WARNING(
                    f"Creating gdrive folders for {websites.count()} websites if they do not already exist..."
                )
            )

            count = 0
            for website in websites:
                new_drive_created = api.create_gdrive_folders(website.short_id)
                if new_drive_created:
                    count += 1

            self.stdout.write(
                "Finished, gdrive folders for {} websites created".format(count)
            )

        else:
            self.stdout.write(self.style.WARNING(f"Google drive credentials not set."))
