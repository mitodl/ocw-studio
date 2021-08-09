from django.conf import settings
from django.core.management import BaseCommand

from gdrive_sync import api
from websites.models import Website


class Command(BaseCommand):
    """Creates a gdrive folder for video uploads for websites that don't already have one"""

    help = __doc__

    def handle(self, *args, **options):
        if settings.DRIVE_SHARED_ID and settings.DRIVE_SERVICE_ACCOUNT_CREDS:
            websites = Website.objects.filter(owner_id__isnull=False)

            self.stdout.write(
                self.style.WARNING(
                    f"Creating gdrive folders for {websites.count()} website objects if they do not already exist..."
                )
            )

            count = 0
            for website in websites:
                new_drive_created = api.create_gdrive_folder_if_not_exists(
                    website.short_id, website.name
                )
                if new_drive_created:
                    count += 1

            self.stdout.write(
                "Creation of website folders finished, {} new folders created".format(
                    count
                )
            )

        else:
            self.stdout.write(self.style.WARNING(f"Google drive credentials not set."))
