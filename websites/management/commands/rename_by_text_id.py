from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand
from django.utils.text import slugify

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
        obj = WebsiteContent.objects.get(text_id=options["text_id"])
        df = DriveFile.objects.get(resource=obj)
        s3 = get_boto3_resource("s3")
        # slugify just the provided name and then make the extensions lowercase
        filepath = Path(options["new_filename"])
        basename = options["new_filename"].rstrip("".join(filepath.suffixes))
        new_filename = slugify(basename)
        if filepath.suffixes:
            new_filename += "".join(filepath.suffixes).lower()
        df_path = df.s3_key.split("/")
        df_path[-1] = new_filename
        new_key = "/".join(df_path)
        s3.Object(settings.AWS_STORAGE_BUCKET_NAME, new_key).copy_from(
            CopySource=settings.AWS_STORAGE_BUCKET_NAME + "/" + df.s3_key
        )
        s3.Object(settings.AWS_STORAGE_BUCKET_NAME, df.s3_key).delete()
        df.s3_key = new_key
        obj.file = new_key
        obj.filename = get_dirpath_and_filename(new_filename)[1]
        df.save()
        obj.save()
