"""Facilitates regex-based replacements on WebsiteContentMarkdown."""
import csv
import re
from dataclasses import asdict, dataclass, fields
from typing import Any

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
)
from websites.management.commands.markdown_cleaning.utils import (
    get_rootrelative_url_from_content,
)
from websites.models import WebsiteContent


class WebsiteContentMarkdownCleaner:
    """Facilitates replacements on WebsiteContent markdown.

    Args:
        rule: A MarkdownCleanupRule instance.
    
    The cleaner instance will make replacements using the given rule and record
    information about each replacement. These records may be recovered via the
    `write_matches_to_csv` method.
    """

    @dataclass
    class ReplacementMatch:
        """Stores data about each replacement made."""

        original_text: str
        replacement: str
        content: WebsiteContent
        notes: Any  # should be a dataclass

    csv_metadata_fieldnames = [
        "original_text",
        "replacement",
        "has_changed",
        "replaced_on_site_name",
        "replaced_on_site_short_id",
        "replaced_on_page_uuid",
        "replaced_on_page_url",
    ]

    def __init__(self, rule: MarkdownCleanupRule):
        self.rule = rule
        self.replacement_matches: "list[WebsiteContentMarkdownCleaner.ReplacementMatch]" = (
            []
        )
        self.updated_website_contents: "list[WebsiteContent]" = []
        self.updated_sync_states: "list[ContentSyncState]" = []

    def store_match_data(
        self,
        original_text: str,
        replacement: str,
        website_content: WebsiteContent,
        notes,
    ):
        """Store match data for subsequent csv-generation."""
        self.replacement_matches.append(
            self.ReplacementMatch(
                original_text,
                replacement=replacement,
                content=website_content,
                notes=notes,
            )
        )
        return replacement

    def update_website_content_markdown(self, website_content: WebsiteContent):
        """
        Updates website_content's markdown and checksums in-place. Does not commit to
        database.
        """
        if not website_content.markdown:
            return

        new_markdown = self.rule.transform_markdown(
            website_content, self.store_match_data
        )
        if new_markdown != website_content.markdown:
            website_content.markdown = new_markdown
            self.updated_website_contents.append(website_content)

            sync_state = website_content.content_sync_state
            if not sync_state:
                return

            new_checksum = website_content.calculate_checksum()
            if new_checksum != sync_state.current_checksum:
                sync_state.current_checksum = new_checksum
                self.updated_sync_states.append(sync_state)

    def write_matches_to_csv(self, path: str):
        """Write matches and replacements to csv."""

        with open(path, "w", newline="") as csvfile:
            fieldnames = [
                *self.csv_metadata_fieldnames,
                *(f.name for f in fields(self.rule.ReplacementNotes)),
            ]
            writer = csv.DictWriter(csvfile, fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for change in self.text_changes:
                row = {
                    "original_text": change.original_text,
                    "replacement": change.replacement,
                    "has_changed": change.original_text != change.replacement,
                    "replaced_on_site_name": change.content.website.name,
                    "replaced_on_site_short_id": change.content.website.short_id,
                    "replaced_on_page_uuid": change.content.text_id,
                    "replaced_on_page_url": get_rootrelative_url_from_content(
                        change.content
                    ),
                    **asdict(change.notes),
                }
                writer.writerow(row)
