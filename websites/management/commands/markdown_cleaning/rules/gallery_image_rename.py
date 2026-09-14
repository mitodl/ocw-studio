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

    Subclasses implement resolve_new_href to decide, for a given website and
    href value, what the href should become (or None to leave it alone). All
    other shortcode params are preserved verbatim.
    """

    Parser = ShortcodeParser

    def should_parse(self, text: str):
        return GALLERY_ITEM_SHORTCODE_NAME in text

    def resolve_new_href(self, website_id, href: str) -> str | None:
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
        new_href = self.resolve_new_href(website_content.website_id, href)
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

    A href is only rewritten once two independent checks agree the rename
    really happened:

    1. Database: the stripped basename exists as a current file in the same
       website, and the original UUID-prefixed basename does not. A file
       whose rename was skipped for a target-key collision still carries its
       UUID prefix, so it fails this check and is left alone.
    2. S3: the object for the stripped name actually exists in the bucket.
       The database check alone is only a proxy, and this rule exists to
       repair historical runs, where WebsiteContent.file and S3 may have
       drifted. Rewriting a href on the strength of a database value that S3
       does not back would point the gallery at a key that is not there.

    Anything that cannot be positively confirmed is left untouched -- an
    unfixed href is re-runnable, a wrongly rewritten one is not.
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

    def resolve_new_href(self, website_id, href: str) -> str | None:
        if not href or not UUID_FILENAME_RE.match(href):
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
