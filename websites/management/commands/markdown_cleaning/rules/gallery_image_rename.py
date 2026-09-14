"""Fix image-gallery-item hrefs left pointing at a pre-rename UUID-prefixed filename."""

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
    patching, or a separate operator session). A href is only rewritten when
    current data confirms the rename actually happened: the stripped
    basename exists as a current file in the same website, and the original
    UUID-prefixed basename does not. This avoids touching hrefs for files
    that were skipped due to a collision.
    """

    alias = "gallery_image_rename"

    def __init__(self):
        super().__init__()
        self._basenames_by_website: dict[str, set[str]] = {}

    def _basenames_for_website(self, website_id) -> set[str]:
        key = str(website_id)
        if key not in self._basenames_by_website:
            files = (
                WebsiteContent.objects.filter(website_id=website_id)
                .exclude(file="")
                .values_list("file", flat=True)
            )
            self._basenames_by_website[key] = {
                f.lstrip("/").rpartition("/")[2] for f in files if f
            }
        return self._basenames_by_website[key]

    def resolve_new_href(self, website_id, href: str) -> str | None:
        if not href or not UUID_FILENAME_RE.match(href):
            return None
        candidate = strip_uuid_prefix(href)
        if candidate == href:
            return None
        basenames = self._basenames_for_website(website_id)
        if candidate in basenames and href not in basenames:
            return candidate
        return None
