"""Fix image-gallery-item hrefs left pointing at a pre-rename UUID-prefixed filename."""

import logging
import re

from django.conf import settings

from main.s3_utils import get_boto3_client
from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.shortcode_parser import (
    ShortcodeParser,
    ShortcodeParseResult,
)
from websites.models import WebsiteContent
from websites.utils import UUID_FILENAME_RE, strip_uuid_prefix

log = logging.getLogger(__name__)

GALLERY_ITEM_SHORTCODE_NAME = "image-gallery-item"

# The href value, quoted either way or bare. Captured so only that span is
# replaced, leaving the rest of the tag exactly as the author wrote it. The
# lookbehind keeps the match from starting inside a longer parameter name, so
# a data-href sitting before the real href cannot be rewritten in its place.
_HREF_VALUE_RE = re.compile(
    r"""(?<![\w-])href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))"""
)


def _splice_href(original_text: str, new_href: str) -> str:
    """
    Replace only the href value inside *original_text*.

    Rebuilding the tag through ShortcodeTag.to_hugo() would round-trip every
    other param too, which both risks mangling anything the parser did not
    capture losslessly (a value carrying a newline tokenises apart, a
    single-quoted one keeps its quotes) and rewrites incidental spacing and
    quote style. Editing the one span leaves the rest byte for byte, so an
    item written in a non-canonical style is still repaired rather than
    skipped.
    """
    match = _HREF_VALUE_RE.search(original_text)
    if match is None:
        return original_text
    group = next(i for i in (1, 2, 3) if match.group(i) is not None)
    if '"' in new_href or "'" in new_href:
        # Would break out of the quoting. No real basename looks like this.
        log.warning("Gallery href fix: refusing a quote-bearing href %s", new_href)
        return original_text
    start, end = match.span(group)
    return f"{original_text[:start]}{new_href}{original_text[end:]}"


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

    def transform_text(self, website_content, text, on_match):
        """
        Parse and rewrite, treating unparseable markdown as nothing to do.

        ShortcodeParser raises on constructs like an unquoted nested
        shortcode. markdown_cleanup's loop has no per-record handling, so
        letting that escape would abort a backfill part way through, after
        earlier pages had already been saved, and leave the rest unrepaired.
        """
        # Buffered rather than passed straight through: the parse action fires
        # per shortcode as it goes, so a valid item sitting before a malformed
        # one would already have been recorded when the exception lands. The
        # page is then left unchanged while --out still reports the row, a
        # change the operator can never find applied.
        buffered = []
        try:
            result = super().transform_text(
                website_content, text, lambda *args: buffered.append(args)
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Gallery href fix: skipping content %s, markdown did not parse (%s)",
                website_content.pk,
                exc,
            )
            return text
        for args in buffered:
            on_match(*args)
        return result

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
        if not href:
            # An item can legitimately carry no href. Guarded here rather than
            # in each resolver so one such item cannot take down the parse for
            # the whole page it sits on.
            return original_text
        # ShortcodeParam only unwraps double quotes, so a single-quoted value
        # still arrives with its quotes attached and would not match the UUID
        # pattern. _HREF_VALUE_RE handles that spelling, so the resolver has to
        # see the same value the author meant.
        if len(href) > 1 and href[0] == href[-1] == "'":
            href = href[1:-1]
        new_href = self.resolve_new_href(
            website_content.website_id, href, shortcode.get("uuid")
        )
        if new_href is None:
            return original_text

        return _splice_href(original_text, new_href)


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
        self._site_cache = {}
        self._key_exists: dict[str, bool] = {}
        self._s3_client = None

    def _site_maps(self, website_id):
        """
        Return this website's files as (basename -> S3 keys, text_id -> S3 key).

        Both lookups come from one query per website, cached for the life of
        the rule. A repair run walks every gallery page in a site and one
        image is usually referenced by several of them, so resolving per item
        would mean a query per reference.
        """
        cache_key = str(website_id)
        if cache_key not in self._site_cache:
            # Every text_id in the site, whether or not it currently has a
            # file and including soft-deleted rows. A uuid that names anything
            # here is a real reference, so the basename guess must not be
            # allowed to answer for it and land on an unrelated image.
            known_text_ids = {
                str(text_id)
                for text_id in WebsiteContent.all_objects.filter(
                    website_id=website_id
                ).values_list("text_id", flat=True)
                if text_id
            }
            rows = (
                WebsiteContent.objects.filter(website_id=website_id)
                .exclude(file="")
                .values_list("file", "text_id")
            )
            by_basename: dict[str, set[str]] = {}
            by_text_id: dict[str, str] = {}
            for file_value, text_id in rows:
                if not file_value:
                    continue
                # Legacy values may be stored as /courses/...; S3 keys never
                # start with a slash.
                s3_key = file_value.lstrip("/")
                by_basename.setdefault(s3_key.rpartition("/")[2], set()).add(s3_key)
                if text_id:
                    by_text_id[str(text_id)] = s3_key
            self._site_cache[cache_key] = (by_basename, by_text_id, known_text_ids)
        return self._site_cache[cache_key]

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

    def _resolve_by_uuid(self, website_id, basename: str, uuid: str) -> str | None:
        """
        Resolve the target from the item's uuid param.

        Scoped to the one website because text_id is unique per website, not
        globally, so a match in another site is not the intended target.
        Deleted resources never enter the map, since it is built through the
        default manager: a href should not be pointed at content that is on
        its way out.
        """
        _, by_text_id, _ = self._site_maps(website_id)
        s3_key = by_text_id.get(uuid)
        if not s3_key:
            return None
        current = s3_key.rpartition("/")[2]
        if current == basename:
            # Not renamed (a collision skip, or already correct).
            return None
        if not self._exists_in_s3({s3_key}):
            return None
        return current

    def _resolve_by_basename(self, website_id, basename: str) -> str | None:
        """Resolve the target by stripping the prefix off the href basename."""
        if not UUID_FILENAME_RE.match(basename):
            return None
        candidate = strip_uuid_prefix(basename)
        if candidate == basename:
            return None
        by_basename, _, _ = self._site_maps(website_id)
        # Database check first -- it is a local dict lookup, so a file ruled
        # out here costs no S3 call.
        if candidate not in by_basename or basename in by_basename:
            return None
        if not self._exists_in_s3(by_basename[candidate]):
            return None
        return candidate

    def resolve_new_href(self, website_id, href: str, uuid: str | None) -> str | None:
        if not href:
            return None
        # A rename only ever changes the basename, so match on the basename
        # and put the href's own prefix back. image_gallery_item_uuid accepts
        # a path-valued href, so one can arrive carrying a uuid param.
        prefix, sep, basename = href.rpartition("/")
        _, _, known_text_ids = self._site_maps(website_id)
        if uuid and uuid in known_text_ids:
            # The uuid names a resource in this website, so it is the target,
            # full stop. Falling back to a basename guess when it cannot be
            # confirmed could point the gallery at a different image that
            # happens to own the stripped name.
            new_basename = self._resolve_by_uuid(website_id, basename, uuid)
        else:
            # No uuid, or one that no longer names anything here, so it is
            # stale rather than authoritative.
            new_basename = self._resolve_by_basename(website_id, basename)
        if new_basename is None:
            return None
        return f"{prefix}{sep}{new_basename}"
