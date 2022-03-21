"""Facilitates find-and-replace on WebsiteContent objects."""
import csv
from dataclasses import asdict, dataclass, fields
from functools import partial
from typing import Any

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
)
from websites.management.commands.markdown_cleaning.utils import (
    get_rootrelative_url_from_content,
    remove_prefix,
)
from websites.models import WebsiteContent
from websites.utils import get_dict_field, set_dict_field


class WebsiteContentMarkdownCleaner:
    """Facilitates find-and-replace on WebsiteContent markdown fields.

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
        field: str

    csv_metadata_fieldnames = [
        "original_text",
        "replacement",
        "has_changed",
        "field",
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

    def store_match_data(
        self,
        original_text: str,
        replacement: str,
        website_content: WebsiteContent,
        notes,
        field: str,
    ):
        """Store match data for subsequent csv-generation."""
        self.replacement_matches.append(
            self.ReplacementMatch(
                original_text,
                replacement=replacement,
                content=website_content,
                notes=notes,
                field=field,
            )
        )
        return replacement

    @staticmethod
    def get_field_to_change(website_content: WebsiteContent, field: str):
        if field == "markdown":
            return website_content.markdown
        if field.startswith("metadata."):
            metadata_keypath = remove_prefix(field, "metadata.")
            if website_content.metadata is None:
                return None
            return get_dict_field(website_content.metadata, metadata_keypath)

        raise ValueError(f"Unexpected field value: {field}")

    @staticmethod
    def make_field_change(website_content: WebsiteContent, field: str, new_value: str):
        if field == "markdown":
            website_content.markdown = new_value
            return
        if field.startswith("metadata."):
            metadata_keypath = remove_prefix(field, "metadata.")
            set_dict_field(website_content.metadata, metadata_keypath, new_value)
            return

        raise ValueError(f"Unexpected field value: {field}")

    def update_website_content(self, wc: WebsiteContent):
        """
        Updates website_content's markdown and checksums in-place. Does not commit to
        database.
        """
        changed = False
        for field in self.rule.fields:
            old_text = self.get_field_to_change(wc, field)
            if old_text is None:
                continue
            store_match_data = partial(self.store_match_data, field=field)
            new_text = self.rule.transform_text(wc, old_text, store_match_data)
            if old_text != new_text:
                self.make_field_change(wc, field, new_text)
                changed = True

        return changed

    def write_matches_to_csv(self, path: str, only_changes):
        """Write matches and replacements to csv."""

        with open(path, "w", newline="") as csvfile:
            fieldnames = [
                *self.csv_metadata_fieldnames,
                *(f.name for f in fields(self.rule.ReplacementNotes)),
            ]
            writer = csv.DictWriter(csvfile, fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for change in self.replacement_matches:
                has_changed = change.original_text != change.replacement
                if only_changes and not has_changed:
                    continue
                row = {
                    "original_text": change.original_text,
                    "replacement": change.replacement,
                    "has_changed": has_changed,
                    "field": change.field,
                    "replaced_on_site_name": change.content.website.name,
                    "replaced_on_site_short_id": change.content.website.short_id,
                    "replaced_on_page_uuid": change.content.text_id,
                    "replaced_on_page_url": get_rootrelative_url_from_content(
                        change.content
                    ),
                    **asdict(change.notes),
                }
                writer.writerow(row)
