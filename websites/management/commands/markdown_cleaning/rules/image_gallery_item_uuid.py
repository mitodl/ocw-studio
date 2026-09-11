"""Add resource uuids to image gallery items. See mitodl/hq#13086."""

import posixpath
import re
from dataclasses import dataclass
from uuid import UUID

from websites.constants import CONTENT_TYPE_RESOURCE, RESOURCE_TYPE_IMAGE
from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.parsing_utils import ShortcodeParam
from websites.management.commands.markdown_cleaning.shortcode_parser import (
    ShortcodeParser,
    ShortcodeParseResult,
)
from websites.models import WebsiteContent

ITEM_SHORTCODE = "image-gallery-item"

# Gallery items reference their image by the legacy OCW filename, which is the
# resource's uuid (dashes stripped) followed by the original filename.
UUID_PREFIX_REGEX = re.compile(r"^(?P<hex>[0-9a-fA-F]{32})_.+$")


class ImageGalleryItemUuidRule(PyparsingRule):
    """
    Add a `uuid` param naming the image resource an image-gallery-item points at.

    Purely additive: `href`, `text` and `data-ngdesc` are left in place because
    v2 galleries still render from `href`, and removing them would break those.

        {{< image-gallery-item href="c3e2...eff_diagram.png" text="Fig 1." >}}

    becomes

        {{< image-gallery-item uuid="c3e28341-...-3a1a5bcc0eff"
            href="c3e2...eff_diagram.png" text="Fig 1." >}}

    An item is only rewritten once the uuid is confirmed to name a live image
    resource in the same website as the page. Everything else is left exactly as
    it was and the reason recorded in `outcome`, so a `--out` run reports the
    problems rather than aborting on the first one.
    """

    alias = "image_gallery_item_uuid"

    Parser = ShortcodeParser

    @dataclass
    class ReplacementNotes:
        is_gallery_item: bool = False
        outcome: str = ""
        href: str = ""
        uuid: str = ""
        resolved_type: str = ""
        resolved_resourcetype: str = ""

    def should_parse(self, text: str):
        """Only a few hundred pages site-wide contain a gallery."""
        return ITEM_SHORTCODE in text

    def replace_match(
        self,
        s: str,  # noqa: ARG002
        l: int,  # noqa: ARG002, E741
        toks: ShortcodeParseResult,
        website_content: WebsiteContent,
    ):
        shortcode = toks.shortcode
        original_text = toks.original_text

        if shortcode.name != ITEM_SHORTCODE:
            return original_text, self.ReplacementNotes()

        notes = self.ReplacementNotes(is_gallery_item=True)
        uuid = self._uuid_from_href(shortcode, notes)
        if uuid is not None:
            notes.outcome = self._check_target(uuid, website_content.website_id, notes)
        if notes.outcome != "ok":
            return original_text, notes

        notes.uuid = str(uuid)
        shortcode.params.insert(0, ShortcodeParam(name="uuid", value=str(uuid)))
        return shortcode.to_hugo(), notes

    def _uuid_from_href(self, shortcode, notes):
        """
        Extract the referenced uuid from the item's href.

        Returns None and records why on `notes` when there is nothing to work
        with.
        """
        if shortcode.get("uuid") is not None:
            notes.outcome = "already_has_uuid"
            return None

        href = shortcode.get("href")
        notes.href = href or ""
        if not href:
            notes.outcome = "no_href"
            return None

        match = UUID_PREFIX_REGEX.match(posixpath.basename(href.strip()))
        if not match:
            notes.outcome = "href_no_uuid_prefix"
            return None

        return UUID(match.group("hex"))

    def _check_target(self, uuid: UUID, website_id, notes) -> str:
        """Return the outcome of resolving `uuid` to a live image resource."""
        resource = self._find_in_website(uuid, website_id)
        if resource is None:
            return "cross_site" if self._exists_elsewhere(uuid) else "uuid_not_found"

        metadata = resource.metadata if isinstance(resource.metadata, dict) else {}
        notes.resolved_type = resource.type
        notes.resolved_resourcetype = metadata.get("resourcetype") or ""

        if resource.deleted is not None:
            return "target_deleted"
        if resource.type != CONTENT_TYPE_RESOURCE:
            return "wrong_content_type"
        if notes.resolved_resourcetype != RESOURCE_TYPE_IMAGE:
            return "wrong_resourcetype"
        return "ok"

    def _find_in_website(self, uuid: UUID, website_id):
        """
        Find the referenced content within `website_id`.

        Scoped to the one website deliberately: text_id is unique per
        (website, text_id) and not globally, so a match in another site is not
        safe to treat as the intended target.

        Matched on the canonical dashed spelling alone. Every text_id in
        production carries dashes, and `unique_text_id` covers the exact pair,
        so this returns at most one row. Accepting an undashed spelling as well
        would allow two rows in one website to normalise to the same uuid, and
        the lookup would then have to guess which of them the emitted dashed
        uuid actually names.
        """
        return WebsiteContent.all_objects.filter(
            website_id=website_id, text_id=str(uuid)
        ).first()

    def _exists_elsewhere(self, uuid: UUID):
        """Distinguish a dangling uuid from one belonging to a different site."""
        return WebsiteContent.all_objects.filter(text_id=str(uuid)).exists()
