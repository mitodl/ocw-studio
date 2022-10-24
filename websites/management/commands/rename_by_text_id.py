import boto3
from django.conf import settings
from django.core.management import BaseCommand

from gdrive_sync.models import DriveFile
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
        s3 = boto3.resource("s3")
        new_filename = options["new_filename"]
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
