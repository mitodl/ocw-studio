"""Back-populate video_captions_resources / video_transcript_resources for orphaned legacy caption/transcript files"""  # noqa: E501, INP001

from collections import namedtuple

from botocore.exceptions import ClientError
from django.conf import settings

from main.management.commands.filter import WebsiteFilterCommand
from main.s3_utils import get_boto3_resource
from main.utils import get_base_filename, get_file_extension
from videos.utils import parse_caption_language_locale
from websites.api import get_valid_new_filename
from websites.constants import (
    CONTENT_FILENAME_MAX_LEN,
    CONTENT_TITLE_MAX_LEN,
    CONTENT_TYPE_RESOURCE,
)
from websites.models import Website, WebsiteContent
from websites.site_config_api import SiteConfig

FieldConfig = namedtuple(  # noqa: PYI024
    "FieldConfig",
    ["file_field", "resource_field", "suffix", "resourcetype", "file_type"],
)

_FIELD_CONFIG = (
    FieldConfig(
        file_field="video_captions_file",
        resource_field="video_captions_resources",
        suffix="captions",
        resourcetype="Other",
        file_type="application/x-subrip",
    ),
    FieldConfig(
        file_field="video_transcript_file",
        resource_field="video_transcript_resources",
        suffix="transcript",
        resourcetype="Document",
        file_type="application/pdf",
    ),
)

# Flushed periodically rather than once at the end, so a crash partway
# through a run (e.g. a transient S3 error) only loses the current batch's
# work instead of every row processed so far.
_BULK_UPDATE_BATCH_SIZE = 500


def _load_s3_object(s3, bucket_name, key):
    """Return the loaded S3 object, or None if it doesn't exist."""
    obj = s3.Object(bucket_name, key)
    try:
        obj.load()
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return None
        raise
    return obj


class Command(WebsiteFilterCommand):
    """
    Back-populate video_captions_resources / video_transcript_resources for
    video resources whose legacy _file path was left orphaned by migration
    0074 (no matching WebsiteContent found at the time). Also removes
    empty-string _file leftovers from the pre-relation-widget string field,
    which 0074's falsy-value guard correctly skipped but never cleaned up.

    Three cases handled per video:

    1. Empty-string _file value (e.g. video_captions_file == ""): no
       caption/transcript was ever set for this video. The key is simply
       removed, there is nothing to back-fill.

    2. A resource in the same language is already linked in the
       corresponding _resources field: GDrive's filename-convention
       auto-link and the scheduled 3Play sync both populate _resources
       independently of this command and never clean up the legacy _file
       key afterward, so a video can already have a current, correctly-
       linked resource while _file is still sitting there stale. Since
       legacy _file values predate per-language suffixes and always resolve
       to "en", such a case means the field is already resolved -- the _file
       key is dropped without creating or linking anything, rather than
       adding a same-language duplicate. A different-language existing
       entry (e.g. an "fr" caption) does not block this: the orphan is
       still linked alongside it.

    3. Non-empty orphan _file path, no same-language resource linked yet:
       the stored path is relative to the *publish* bucket (prefixed by the
       website's url_path), while WebsiteContent.file and the storage
       bucket are keyed relative to the website's s3_path
       (site_config.root_url_path + website.name). When url_path differs
       from s3_path, the path is converted to its storage key before any
       lookup, mirroring the same swap WebsiteContent.full_metadata does in
       reverse when generating the published path. If a WebsiteContent
       resource already points at that storage key (e.g. created by a later
       sync or manual remediation after migration 0074 ran), that resource
       is reused rather than creating a duplicate. Otherwise, the
       referenced S3 object may still exist even though no WebsiteContent
       record was ever created for it (e.g. content uploaded directly to S3
       outside of the GDrive/3Play pipelines, using a Google Drive file ID
       as the filename); if so, a new WebsiteContent resource is created
       for it, named with the same convention GDrive ingestion uses --
       the video's base stem plus the caption/transcript suffix plus the
       real file extension, e.g. "lecture1_captions_vtt" for a video named
       "lecture1_mp4" (truncated as needed to fit the filename length
       limit). The orphan path's own filename is not used, since it is
       often an opaque identifier. Matching GDrive's convention matters:
       auto_link_video_captions_transcript and
       Video.caption_transcript_resources() both discover resources by the
       "{base_stem}_captions" / "{base_stem}_transcript" prefix, so a
       resource named any other way is invisible to them and gets
       re-fetched from 3Play as a duplicate. If
       the S3 object no longer exists under the storage key, the _file path
       is left in place for manual inspection. Either way, the resolved
       resource's id is appended to the resource field's existing content
       list without dropping an already-linked id, whether that existing
       value is a list or a legacy scalar string.

    IMPORTANT: do not run this against production data until the
    remove_uuid_from_filenames management command has been run against
    production data.
    """

    help = __doc__

    @staticmethod
    def _truncate_with_suffix(base, suffix, max_length):
        """Truncate base so f"{base}{suffix}" fits within max_length."""
        max_base_len = max_length - len(suffix)
        return f"{base[:max_base_len]}{suffix}"

    @staticmethod
    def _to_storage_key(website, path):
        """Convert a url_path-relative orphan path to its s3_path storage key.

        Mirrors WebsiteContent.full_metadata's equivalent swap in reverse.
        Leaves the path unchanged if the swap can't be determined (no
        starter, so s3_path can't be computed) or doesn't apply (no
        url_path, prefixes already match, or the path doesn't actually
        start with url_path).
        """
        key = path.lstrip("/")
        url_path = website.url_path
        if not url_path or website.starter is None:
            return key
        s3_path = website.s3_path
        if s3_path != url_path and key.startswith(url_path):
            key = s3_path + key[len(url_path) :]
        return key

    def _resolve_or_create_resource(self, content, key, path, field_config):
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
        s3_object = _load_s3_object(self.s3, bucket_name, key)
        if s3_object is None:
            self.stdout.write(
                f"Skipping missing S3 object for "
                f"{content.website.name}/{content.filename}: {path}"
            )
            return None

        # Name the created resource exactly as GDrive ingestion and
        # link_threeplay_files_as_resources would: the video's *base stem*
        # (get_base_filename strips the trailing format tag, e.g.
        # "lecture1_mp4" -> "lecture1") plus the caption/transcript suffix
        # plus the real file extension, giving "lecture1_captions_vtt".
        # auto_link_video_captions_transcript and
        # Video.caption_transcript_resources() both search the
        # "{base_stem}_captions" / "{base_stem}_transcript" prefix, so
        # anything named off the *full* filename would be invisible to them
        # and get re-fetched from 3Play as a duplicate. The orphan path's own
        # filename is not used because it is often an opaque identifier.
        #
        # Truncated so the suffixed base never exceeds the filename length
        # limit on its own, before get_valid_new_filename handles any
        # additional numbered-suffix truncation needed for a collision.
        suffix = f"_{field_config.suffix}"
        if extension := get_file_extension(key):
            suffix = f"{suffix}_{extension}"
        base_filename = self._truncate_with_suffix(
            get_base_filename(content.filename), suffix, CONTENT_FILENAME_MAX_LEN
        )
        filename = get_valid_new_filename(
            website_pk=content.website_id,
            dirpath=content.dirpath,
            filename_base=base_filename,
        )
        title = (
            self._truncate_with_suffix(
                content.title, f" {field_config.suffix}", CONTENT_TITLE_MAX_LEN
            )
            if content.title
            else filename
        )
        # Same schema-defaulted metadata GDrive sync uses (draft,
        # learning_resource_types, gdrive_url, etc. all get their configured
        # defaults), instead of a bare {file, resourcetype} dict. Falls back
        # to the bare shape if there's no starter to read a schema from.
        resource_type_fields = {
            "file_type": field_config.file_type,
            "file_size": s3_object.content_length,
            **dict.fromkeys(settings.RESOURCE_TYPE_FIELDS, field_config.resourcetype),
        }
        if content.website.starter is not None:
            metadata = {
                **SiteConfig(content.website.starter.config).generate_item_metadata(
                    CONTENT_TYPE_RESOURCE,
                    cls=WebsiteContent,
                    use_defaults=True,
                    values=resource_type_fields,
                    website_name=content.website.name,
                ),
                "file": path,
            }
        else:
            metadata = {"file": path, **resource_type_fields}
        return WebsiteContent.objects.create(
            website_id=content.website_id,
            type="resource",
            is_page_content=True,
            filename=filename,
            dirpath=content.dirpath,
            file=key,
            title=title,
            metadata=metadata,
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

    @staticmethod
    def _existing_resource_languages(video_files, resource_field, website_id):
        """Return the set of languages already linked for resource_field.

        Videos, GDrive's filename-convention auto-link, and the scheduled
        3Play sync can all populate this field independently of this
        command, and none of them clean up the legacy _file key afterward.
        """
        existing = video_files.get(resource_field)
        if not isinstance(existing, dict):
            return set()
        content = existing.get("content")
        if isinstance(content, str):
            text_ids = [content] if content else []
        elif isinstance(content, list):
            text_ids = content
        else:
            return set()
        if not text_ids:
            return set()

        return {
            parse_caption_language_locale(file_name)[0]
            for file_name in WebsiteContent.objects.filter(
                website_id=website_id, text_id__in=text_ids
            ).values_list("file", flat=True)
            if file_name
        }

    def _backfill_video(self, content):
        """Back-fill one video's orphaned _file fields. Returns True if changed."""
        video_files = content.metadata.get("video_files")
        if not isinstance(video_files, dict):
            return False

        changed = False

        for field_config in _FIELD_CONFIG:
            path = video_files.get(field_config.file_field)
            if not isinstance(path, str):
                continue

            # Case 1: empty-string leftover, nothing to back-fill, just drop it.
            if not path:
                video_files.pop(field_config.file_field)
                changed = True
                continue

            key = self._to_storage_key(content.website, path)

            # Case 1b: a resource is already linked for the same language
            # this orphan would resolve to. It was linked by something
            # other than this command (legacy _file values predate
            # language suffixes, so they always resolve to "en" by
            # convention) -- that link is authoritative for this language,
            # so drop the stale _file value rather than adding a duplicate.
            # A different-language existing entry (e.g. an "fr" caption) is
            # left alone and the orphan is still linked alongside it.
            orphan_language, _ = parse_caption_language_locale(key)
            existing_languages = self._existing_resource_languages(
                video_files, field_config.resource_field, content.website_id
            )
            if orphan_language in existing_languages:
                video_files.pop(field_config.file_field)
                changed = True
                continue

            # Case 2: real orphan path, no same-language resource linked
            # yet. Reuse a resource already pointing at this exact S3 key
            # if one exists (e.g. created by a later sync or manual
            # remediation after migration 0074 ran) instead of creating a
            # duplicate; otherwise verify the object still exists in S3 and
            # create a new resource for it.
            resource = self._resolve_or_create_resource(
                content, key, path, field_config
            )
            if resource is None:
                continue

            self._merge_resource_into_video_files(
                video_files, field_config.resource_field, resource, content.website.name
            )
            video_files.pop(field_config.file_field)
            changed = True

        return changed

    @staticmethod
    def _flush(objects_to_update, website_ids):
        """Persist one batch's metadata writes and website flags together."""
        WebsiteContent.objects.bulk_update(objects_to_update, ["metadata"])
        Website.objects.filter(pk__in=website_ids).update(
            has_unpublished_draft=True,
            has_unpublished_live=True,
        )

    def handle(self, *args, **options):
        """Run the backfill."""
        super().handle(*args, **options)

        self.s3 = get_boto3_resource("s3")
        total_updated = 0
        all_updated_website_ids = set()
        objects_to_update = []
        batch_website_ids = set()
        website_qset = self.filter_websites(Website.objects.all())

        content_qset = (
            WebsiteContent.objects.filter(
                website__in=website_qset,
                metadata__resourcetype="Video",
                metadata__video_files__isnull=False,
            )
            .select_related("website", "website__starter")
            .only(
                "id",
                "filename",
                "dirpath",
                "title",
                "metadata",
                "website__name",
                "website__url_path",
                "website__starter__config",
            )
        )

        # Not a small, curated set: this matches every video with a
        # video_files key across every website, in the thousands on real
        # data, so .iterator() avoiding loading the whole queryset into
        # memory at once matters here.
        for content in content_qset.iterator():
            if self._backfill_video(content):
                objects_to_update.append(content)
                batch_website_ids.add(content.website_id)

            if len(objects_to_update) >= _BULK_UPDATE_BATCH_SIZE:
                self._flush(objects_to_update, batch_website_ids)
                total_updated += len(objects_to_update)
                all_updated_website_ids |= batch_website_ids
                objects_to_update = []
                batch_website_ids = set()

        if objects_to_update:
            self._flush(objects_to_update, batch_website_ids)
            total_updated += len(objects_to_update)
            all_updated_website_ids |= batch_website_ids

        self.stdout.write(
            f"Backfilled {total_updated} video resources across "
            f"{len(all_updated_website_ids)} websites."
        )
