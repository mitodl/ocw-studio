"""Fix image-gallery-item hrefs left pointing at a pre-rename UUID-prefixed filename."""

import logging

from django.conf import settings

from main.s3_utils import get_boto3_client
from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.parsing_utils import (
    ShortcodeParam,
    ShortcodeTag,
)
from websites.management.commands.markdown_cleaning.shortcode_parser import (
    ShortcodeParser,
    ShortcodeParseResult,
)
from websites.models import WebsiteContent
from websites.utils import UUID_FILENAME_RE, strip_uuid_prefix

log = logging.getLogger(__name__)

GALLERY_ITEM_SHORTCODE_NAME = "image-gallery-item"


class BaseGalleryHrefRewriteRule(PyparsingRule):
    """
    Shared shortcode-rewrite mechanics for image-gallery-item href fixes.

    Subclasses implement resolve_new_href to decide, for a given website,
    href and item uuid, what the href should become (or None to leave it
    alone). All other shortcode params are preserved verbatim, including the
    uuid that image_gallery_item_uuid adds.
    """

    Parser = ShortcodeParser

    def should_parse(self, text: str):
        return GALLERY_ITEM_SHORTCODE_NAME in text

    def resolve_new_href(self, website_id, href: str, uuid: str | None) -> str | None:
        raise NotImplementedError

    def replace_match(
        self,
        s,  # noqa: ARG002
        l,  # noqa: ARG002, E741
        toks: ShortcodeParseResult,
        website_content: WebsiteContent,
    ):
        shortcode = toks.shortcode
        original_text = toks.original_text

        if shortcode.name != GALLERY_ITEM_SHORTCODE_NAME:
            return original_text

        href = shortcode.get("href")
        new_href = self.resolve_new_href(
            website_content.website_id, href, shortcode.get("uuid")
        )
        if new_href is None:
            return original_text

        new_params = [
            ShortcodeParam(name=p.name, value=new_href) if p.name == "href" else p
            for p in shortcode.params
        ]
        new_shortcode = ShortcodeTag(
            name=shortcode.name,
            params=new_params,
            percent_delimiters=shortcode.percent_delimiters,
            closer=shortcode.closer,
        )
        return new_shortcode.to_hugo()


class GalleryImageRenameRule(BaseGalleryHrefRewriteRule):
    """
    Standalone repair pass for markdown_cleanup: infers renames from current
    WebsiteContent state rather than a live rename batch.

    For use as a backfill when remove_uuid_from_filenames already ran and
    left gallery markdown stale (e.g. runs that predate gallery-href
    patching, or a separate operator session).

    The target is resolved two ways, in order of how much the data pins it
    down:

    1. By the item's uuid param, which image_gallery_item_uuid records as the
       image resource's text_id. That names the resource outright, so its
       current file is authoritative no matter what the href says. A rename
       skipped for a target-key collision needs no special case here: the
       file still carries its prefix, so the href already matches and nothing
       changes.
    2. By basename, for items the uuid backfill left alone. The stripped
       basename must exist as a current file in the same website and the
       UUID-prefixed original must not, which is what keeps
       collision-skipped files out.

    Either way the object is then confirmed present in S3 before the href is
    rewritten. The database is only a proxy for what the bucket holds, and
    this rule exists to repair historical runs, where the two may have
    drifted. Anything that cannot be positively confirmed is left untouched:
    an unfixed href is re-runnable, a wrongly rewritten one is not.
    """

    alias = "gallery_image_rename"

    def __init__(self):
        super().__init__()
        self._keys_by_website: dict[str, dict[str, set[str]]] = {}
        self._key_exists: dict[str, bool] = {}
        self._s3_client = None

    def _keys_for_website(self, website_id) -> dict[str, set[str]]:
        """Map each file basename in *website_id* to its normalized S3 keys."""
        cache_key = str(website_id)
        if cache_key not in self._keys_by_website:
            files = (
                WebsiteContent.objects.filter(website_id=website_id)
                .exclude(file="")
                .values_list("file", flat=True)
            )
            by_basename: dict[str, set[str]] = {}
            for file_value in files:
                if not file_value:
                    continue
                # Legacy values may be stored as /courses/...; S3 keys never
                # start with a slash.
                s3_key = file_value.lstrip("/")
                by_basename.setdefault(s3_key.rpartition("/")[2], set()).add(s3_key)
            self._keys_by_website[cache_key] = by_basename
        return self._keys_by_website[cache_key]

    def _exists_in_s3(self, s3_keys: set[str]) -> bool:
        """
        Return True if any of *s3_keys* is a real object in the storage bucket.

        Results are cached per key: one renamed image is typically referenced
        by several gallery pages, and a full repair run scans thousands of
        them.
        """
        if self._s3_client is None:
            self._s3_client = get_boto3_client("s3")
        for s3_key in sorted(s3_keys):
            if s3_key not in self._key_exists:
                try:
                    self._s3_client.head_object(
                        Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=s3_key
                    )
                except Exception as exc:  # noqa: BLE001
                    # Either the object is gone (database/S3 drift) or the
                    # lookup itself failed. Neither confirms the rename.
                    log.warning(
                        "Gallery href fix: could not confirm S3 object %s (%s)",
                        s3_key,
                        exc,
                    )
                    self._key_exists[s3_key] = False
                else:
                    self._key_exists[s3_key] = True
            if self._key_exists[s3_key]:
                return True
        return False

    def _resolve_by_uuid(self, website_id, href: str, uuid: str) -> str | None:
        """
        Resolve the target from the item's uuid param.

        Scoped to the one website because text_id is unique per website, not
        globally, so a match in another site is not the intended target.
        Deleted resources are excluded by the default manager: a href should
        not be pointed at content that is on its way out.
        """
        resource = (
            WebsiteContent.objects.filter(website_id=website_id, text_id=uuid)
            .exclude(file="")
            .first()
        )
        if resource is None or not resource.file:
            return None
        s3_key = str(resource.file).lstrip("/")
        basename = s3_key.rpartition("/")[2]
        if basename == href:
            # Not renamed (a collision skip, or already correct).
            return None
        if not self._exists_in_s3({s3_key}):
            return None
        return basename

    def _resolve_by_basename(self, website_id, href: str) -> str | None:
        """Resolve the target by stripping the prefix off the href itself."""
        if not UUID_FILENAME_RE.match(href):
            return None
        candidate = strip_uuid_prefix(href)
        if candidate == href:
            return None
        keys_by_basename = self._keys_for_website(website_id)
        # Database check first -- it is a local dict lookup, so a file ruled
        # out here costs no S3 call.
        if candidate not in keys_by_basename or href in keys_by_basename:
            return None
        if not self._exists_in_s3(keys_by_basename[candidate]):
            return None
        return candidate

    def resolve_new_href(self, website_id, href: str, uuid: str | None) -> str | None:
        if not href:
            return None
        if uuid:
            resolved = self._resolve_by_uuid(website_id, href, uuid)
            if resolved is not None:
                return resolved
            # A uuid that no longer names a resource here is stale rather than
            # authoritative, so fall through to the basename check.
        return self._resolve_by_basename(website_id, href)
