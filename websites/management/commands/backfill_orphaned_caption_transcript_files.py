"""Back-populate video_captions_resources / video_transcript_resources for orphaned legacy caption/transcript files"""  # noqa: E501, INP001

import uuid

from botocore.exceptions import ClientError
from django.conf import settings

from main.management.commands.filter import WebsiteFilterCommand
from main.s3_utils import get_boto3_resource
from websites.api import get_valid_new_filename
from websites.constants import CONTENT_FILENAME_MAX_LEN, CONTENT_TITLE_MAX_LEN
from websites.models import Website, WebsiteContent

# Each entry: file_field, resource_field, filename_suffix, resourcetype.
_FIELD_CONFIG = (
    ("video_captions_file", "video_captions_resources", "captions", "Other"),
    ("video_transcript_file", "video_transcript_resources", "transcript", "Document"),
)


def _object_exists_in_s3(s3, bucket_name, key):
    """Return True if the S3 object exists."""
    try:
        s3.Object(bucket_name, key).load()
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise
    return True


class Command(WebsiteFilterCommand):
    """
    Back-populate video_captions_resources / video_transcript_resources for
    video resources whose legacy _file path was left orphaned by migration
    0074 (no matching WebsiteContent found at the time). Also removes
    empty-string _file leftovers from the pre-relation-widget string field,
    which 0074's falsy-value guard correctly skipped but never cleaned up.

    Two cases handled per video:

    1. Empty-string _file value (e.g. video_captions_file == ""): no
       caption/transcript was ever set for this video. The key is simply
       removed, there is nothing to back-fill.

    2. Non-empty orphan _file path: if a WebsiteContent resource already
       points at this exact S3 key (e.g. created by a later sync or manual
       remediation after migration 0074 ran), that resource is reused rather
       than creating a duplicate. Otherwise, the referenced S3 object may
       still exist even though no WebsiteContent record was ever created for
       it (e.g. content uploaded directly to S3 outside of the GDrive/3Play
       pipelines, using a Google Drive file ID as the filename); if so, a new
       WebsiteContent resource is created for it, named after the video's own
       filename (truncated as needed to fit the filename length limit)
       rather than the orphan path's filename, since the orphan path is often
       an opaque identifier. If the S3 object no longer exists, the _file
       path is left in place for manual inspection. Either way, the resolved
       resource's id is appended to the resource field's existing content
       list without dropping an already-linked id, whether that existing
       value is a list or a legacy scalar string.

    IMPORTANT: do not run this against production data until the
    remove_uuid_from_filenames management command has been run against
    production data.
    """

    help = __doc__

    @staticmethod
    def _build_title(content_title, suffix, filename):
        """Build the new resource's title, truncated to fit the title column."""
        if not content_title:
            return filename
        suffix_part = f" {suffix}"
        max_base_len = CONTENT_TITLE_MAX_LEN - len(suffix_part)
        return f"{content_title[:max_base_len]}{suffix_part}"

    def _resolve_or_create_resource(self, content, key, path, suffix, resourcetype):
        """Find a resource already pointing at this S3 key, or create one.

        Returns None if the S3 object no longer exists (the orphan path is
        left in place for manual inspection in that case).
        """
        resource = WebsiteContent.objects.filter(
            website_id=content.website_id, file=key
        ).first()
        if resource is not None:
            return resource

        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        if not _object_exists_in_s3(self.s3, bucket_name, key):
            self.stdout.write(
                f"Skipping missing S3 object for "
                f"{content.website.name}/{content.filename}: {path}"
            )
            return None

        # Truncate the video's own filename so the suffixed base never
        # exceeds the filename length limit on its own, before
        # get_valid_new_filename handles any additional numbered-suffix
        # truncation needed for a collision.
        suffix_part = f"_{suffix}"
        max_base_len = CONTENT_FILENAME_MAX_LEN - len(suffix_part)
        base_filename = f"{content.filename[:max_base_len]}{suffix_part}"
        filename = get_valid_new_filename(
            website_pk=content.website_id,
            dirpath=content.dirpath,
            filename_base=base_filename,
        )
        title = self._build_title(content.title, suffix, filename)
        return WebsiteContent.objects.create(
            website_id=content.website_id,
            type="resource",
            is_page_content=True,
            filename=filename,
            dirpath=content.dirpath,
            file=key,
            text_id=str(uuid.uuid4()),
            title=title,
            metadata={
                "file": path,
                "resourcetype": resourcetype,
            },
        )

    def _merge_resource_into_video_files(
        self, video_files, resource_field, resource, website_name
    ):
        """Append resource's id to video_files[resource_field], no duplicates."""
        existing = video_files.get(resource_field)
        existing_ids = []
        if isinstance(existing, dict) and existing.get("content"):
            existing_content = existing["content"]
            existing_ids = (
                [existing_content]
                if isinstance(existing_content, str)
                else list(existing_content)
            )
        resource_text_id = str(resource.text_id)
        if resource_text_id not in existing_ids:
            existing_ids = [*existing_ids, resource_text_id]
        video_files[resource_field] = {
            "content": existing_ids,
            "website": website_name,
        }

    def _backfill_video(self, content):
        """Back-fill one video's orphaned _file fields. Returns True if changed."""
        video_files = content.metadata.get("video_files")
        if not isinstance(video_files, dict):
            return False

        changed = False

        for file_field, resource_field, suffix, resourcetype in _FIELD_CONFIG:
            path = video_files.get(file_field)
            if not isinstance(path, str):
                continue

            # Case 1: empty-string leftover, nothing to back-fill, just drop it.
            if not path:
                video_files.pop(file_field)
                changed = True
                continue

            # Case 2: real orphan path. Reuse a resource already pointing at
            # this exact S3 key if one exists (e.g. created by a later sync
            # or manual remediation after migration 0074 ran) instead of
            # creating a duplicate; otherwise verify the object still exists
            # in S3 and create a new resource for it.
            key = path.lstrip("/")
            resource = self._resolve_or_create_resource(
                content, key, path, suffix, resourcetype
            )
            if resource is None:
                continue

            self._merge_resource_into_video_files(
                video_files, resource_field, resource, content.website.name
            )
            video_files.pop(file_field)
            changed = True

        return changed

    def handle(self, *args, **options):
        """Run the backfill."""
        super().handle(*args, **options)

        self.s3 = get_boto3_resource("s3")
        updated_website_ids = set()
        objects_to_update = []
        website_qset = self.filter_websites(Website.objects.all())

        content_qset = (
            WebsiteContent.objects.filter(
                website__in=website_qset,
                metadata__resourcetype="Video",
                metadata__video_files__isnull=False,
            )
            .select_related("website")
            .only("id", "filename", "dirpath", "title", "metadata", "website__name")
        )

        # Not a small, curated set: this matches every video with a
        # video_files key across every website, in the thousands on real
        # data, so .iterator() avoiding loading the whole queryset into
        # memory at once matters here.
        for content in content_qset.iterator():
            if self._backfill_video(content):
                objects_to_update.append(content)
                updated_website_ids.add(content.website_id)

        if objects_to_update:
            WebsiteContent.objects.bulk_update(objects_to_update, ["metadata"])

        if updated_website_ids:
            Website.objects.filter(pk__in=updated_website_ids).update(
                has_unpublished_draft=True,
                has_unpublished_live=True,
            )

        self.stdout.write(
            f"Backfilled {len(objects_to_update)} video resources across "
            f"{len(updated_website_ids)} websites."
        )
