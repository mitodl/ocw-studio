"""Facilitates find-and-replace on WebsiteContent objects."""

import csv
from dataclasses import asdict, dataclass, fields
from functools import partial
from typing import TYPE_CHECKING, Any

from websites.management.commands.markdown_cleaning.utils import (
    get_rootrelative_url_from_content,
    remove_prefix,
)
from websites.utils import get_dict_field, parse_resource_uuid, set_dict_field

if TYPE_CHECKING:
    from websites.management.commands.markdown_cleaning.cleanup_rule import (
        MarkdownCleanupRule,
    )
    from websites.models import WebsiteContent


def get_ocw_url(content: WebsiteContent):
    """Return an ocw.mit.edu url to the given content."""
    rootrel = get_rootrelative_url_from_content(content)
    return f"https://ocw.mit.edu{rootrel}"


def get_studio_url(content: WebsiteContent):
    """Return an ocw-studio.odl.mit.edu url to the given content."""
    site_name = content.website.name
    if content.type == "sitemetadata":
        return f"https://ocw-studio.odl.mit.edu/sites/{site_name}/type/metadata/"
    return f"https://ocw-studio.odl.mit.edu/sites/{site_name}/type/page/edit/{content.text_id}/"


def get_github_url(content: WebsiteContent):
    """Return a github.mit.edu url to the given content."""
    short_id = content.website.short_id
    return f"https://github.mit.edu/mitocwcontent/{short_id}/tree/main/{content.dirpath}/{content.filename}.md"


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
        url_targets: tuple[int, ...]

    csv_metadata_fieldnames = [
        "original_text",
        "replacement",
        "has_changed",
        "field",
        "replaced_on_site_name",
        "replaced_on_site_short_id",
        "replaced_on_page_uuid",
        "root_relative_url",
        "ocw_url",
        "github_url",
        "studio_url",
    ]

    def __init__(self, rule: MarkdownCleanupRule):
        self.rule = rule
        self.replacement_matches: list[
            WebsiteContentMarkdownCleaner.ReplacementMatch
        ] = []

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
                url_targets=tuple(self.rule.url_targets),
            )
        )
        self.rule.url_targets.clear()
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

        msg = f"Unexpected field value: {field}"
        raise ValueError(msg)

    @staticmethod
    def make_field_change(website_content: WebsiteContent, field: str, new_value: str):
        if field == "markdown":
            website_content.markdown = new_value
            return
        if field.startswith("metadata."):
            metadata_keypath = remove_prefix(field, "metadata.")
            set_dict_field(website_content.metadata, metadata_keypath, new_value)
            return

        msg = f"Unexpected field value: {field}"
        raise ValueError(msg)

    def update_website_content(self, wc: WebsiteContent, *, repair=None):
        """
        Updates website_content's markdown and checksums in-place. Does not commit to
        database.
        """  # noqa: D401
        changed = False
        for field in self.rule.fields:
            old_text = self.get_field_to_change(wc, field)
            if old_text is None:
                continue
            store_match_data = partial(self.store_match_data, field=field)
            first_match = len(self.replacement_matches)
            self.rule.url_targets.clear()
            new_text = self.rule.transform_text(wc, old_text, store_match_data)
            if old_text != new_text:
                self.make_field_change(wc, field, new_text)
                if repair is not None:
                    self.collect_references(repair, first_match, old_text, new_text)
                changed = True

        return changed

    def collect_references(self, repair, first_match, old_text, new_text):
        """Collect dependencies of replacements that made it into the saved field."""
        for match in self.replacement_matches[first_match:]:
            if match.original_text == match.replacement:
                continue
            # Nav items and quoted shortcode links cannot be parsed for a target.
            if target := getattr(match.notes, "external_resource", None):
                targets = {target}
            elif isinstance(match.replacement, str):
                targets = set(parse_resource_uuid(match.replacement)).difference(
                    parse_resource_uuid(match.original_text)
                )
            else:
                targets = set()
            # Matches inside a link label are reported even when the label is kept.
            if not targets and not match.url_targets:
                continue
            if new_text.count(match.replacement) <= old_text.count(match.replacement):
                continue
            source = match.content
            repair.url_references.update((source.pk, pk) for pk in match.url_targets)
            for text_id in targets:
                repair.references.add((source.pk, source.website_id, text_id))

    def write_matches_to_csv(self, path: str, only_changes):
        """Write matches and replacements to csv."""

        with open(path, "w", newline="", encoding="utf-8") as csvfile:  # noqa: PTH123
            fieldnames = [
                *self.csv_metadata_fieldnames,
                *(f.name for f in fields(self.rule.ReplacementNotes)),
            ]
            writer = csv.DictWriter(
                csvfile,
                fieldnames,
                quoting=csv.QUOTE_MINIMAL,
                escapechar="\\",
                doublequote=False,
            )
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
                    "root_relative_url": get_rootrelative_url_from_content(
                        change.content
                    ),
                    "ocw_url": get_ocw_url(change.content),
                    "studio_url": get_studio_url(change.content),
                    "github_url": get_github_url(change.content),
                    **asdict(change.notes),
                }
                writer.writerow(row)
