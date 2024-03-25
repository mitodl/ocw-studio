from django.core.management import BaseCommand  # noqa: INP001

from gdrive_sync.api import rename_file


class Command(BaseCommand):
    """Rename the file on S3 associated with the WebsiteContent object to a new filename, and update the object and corresponding DriveFile."""  # noqa: E501

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

    def handle(self, *args, **options):  # noqa: ARG002
        rename_file(options["text_id"], options["new_filename"])
        self.stdout.write("File successfully renamed.\n")
