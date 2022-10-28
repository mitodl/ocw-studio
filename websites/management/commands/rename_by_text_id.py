from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand
from django.utils.text import slugify

from gdrive_sync.api import rename_file
from gdrive_sync.models import DriveFile
from main.s3_utils import get_boto3_resource
from main.utils import get_dirpath_and_filename
from websites.models import WebsiteContent


class Command(BaseCommand):
    """Rename the file on S3 associated with the WebsiteContent object to a new filename, and update the object and corresponding DriveFile."""

    help = __doc__

    def add_arguments(self, parser):

        parser.add_argument(
            "--text_id",
            dest="text_id",
            help="text_id of WebsiteContent object to be updated",
            required=True,
        )

        parser.add_argument(
            "--new_filename",
            dest="new_filename",
            help="New filename to be associated with the WebsiteContent object",
            required=True,
        )

    def handle(self, *args, **options):
        rename_file(options["text_id"], options["new_filename"])
        self.stdout.write("File successfully renamed.\n")
