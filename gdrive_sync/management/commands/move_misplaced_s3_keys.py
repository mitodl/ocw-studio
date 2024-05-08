from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import Q

from content_sync.tasks import sync_website_content
from gdrive_sync.models import DriveFile
from main.s3_utils import get_boto3_client
from websites.constants import WEBSITE_SOURCE_STUDIO
from websites.models import Website, WebsiteContent


class Command(BaseCommand):
    """Moves nonvideo files mistakenly placed in a `Website.short_id` path to a `Website.name` path"""  # noqa: E501

    help = __doc__  # noqa: A003

    def handle(self, *args, **options):  # noqa: ARG002
        s3 = get_boto3_client("s3")
        for site in Website.objects.filter(source=WEBSITE_SOURCE_STUDIO).values(
            "uuid", "name", "short_id"
        ):
            if site["name"] != site["short_id"]:
                for drive_file in (
                    DriveFile.objects.exclude(video__isnull=False)
                    .filter(
                        Q(website__uuid=site["uuid"])
                        & Q(s3_key__contains=site["short_id"])
                    )
                    .iterator()
                ):
                    old_s3_key = drive_file.s3_key
                    new_s3_key = drive_file.s3_key.replace(
                        f'{drive_file.s3_prefix}/{site["short_id"]}',
                        f'{drive_file.s3_prefix}/{site["name"]}',
                        1,
                    )
                    if old_s3_key == new_s3_key:
                        continue
                    try:
                        self.stdout.write(f"Moving {old_s3_key} to {new_s3_key}")
                        s3.copy_object(
                            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                            CopySource=f"{settings.AWS_STORAGE_BUCKET_NAME}/{old_s3_key}",
                            Key=new_s3_key,
                            ACL="public-read",
                        )
                        s3.delete_object(
                            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                            Key=drive_file.s3_key,
                        )
                        drive_file.s3_key = new_s3_key
                        drive_file.save()
                        content = WebsiteContent.objects.filter(file=old_s3_key).first()
                        if content:
                            content.file = new_s3_key
                            content.save()
                    except Exception as exc:  # noqa: BLE001
                        self.stderr.write(
                            f"Error copying {old_s3_key} to {new_s3_key}: {exc!s}"
                        )
            sync_website_content.delay(site["name"])

        self.stdout.write("Finished moving s3 objects")
