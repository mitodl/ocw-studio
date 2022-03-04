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
    """Facilitates regex-based replacements on WebsiteContent markdown.

    Args:
        rule: A MarkdownCleanupRule instance.

    The given rule specifies a regex and is callable as a replacer function. The
    rule will be called for every non-overlapping match of the regex and should
    return the replacement string. This is similar to the `repl` argument of
    `re.sub`, but is invoked with two arguments `(match, website_content)`,
    instead of just `match`. Here `website_content` is a partial website_content
    object.

    If the pattern uses named capturing groups, these groups will be included as
    csv columns by `write_to_csv()` method.

    Note: Internally records all matches and replacement results for subsequent
    writing to csv.
    """

    @dataclass
    class ReplacementMatch:
        match: re.Match
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
        self.regex = self.compile_regex(rule.regex)
        self.rule = rule

        self.text_changes: "list[WebsiteContentMarkdownCleaner.ReplacementMatch]" = []
        self.updated_website_contents: "list[WebsiteContent]" = []
        self.updated_sync_states: "list[ContentSyncState]" = []

        def _replacer(match: re.Match, website_content: WebsiteContent):
            result = rule(match, website_content)
            if isinstance(result, str):
                replacement = result
                notes = self.rule.ReplacementNotes()
            elif isinstance(result, tuple):
                replacement, notes = result
            else:
                raise ValueError(
                    "MarkdownCleanupRule instances should return strings or tuples when called"
                )

            self.text_changes.append(
                self.ReplacementMatch(
                    match=match,
                    replacement=replacement,
                    content=website_content,
                    notes=notes,
                )
            )
            return replacement

        self.replacer = _replacer

    def update_website_content_markdown(self, website_content: WebsiteContent):
        """
        Updates website_content's markdown and checksums in-place. Does not commit to
        database.
        """
        if not website_content.markdown:
            return

        new_markdown = self.regex.sub(
            lambda match: self.replacer(match, website_content),
            website_content.markdown,
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

    @classmethod
    def compile_regex(cls, pattern):
        """Compile `pattern` and validate that it has no named capturing groups
        whose name would conflict with csv metadata fieldnames."""
        compiled = re.compile(pattern)
        for groupname in cls.csv_metadata_fieldnames:
            if groupname in compiled.groupindex:
                raise ValueError(
                    f"Regex group name {groupname} is reserved for use by {cls.__name__}"
                )
        return compiled

    def write_matches_to_csv(self, path: str):
        """Write matches and replacements to csv."""

        with open(path, "w", newline="") as csvfile:
            fieldnames = [
                *self.csv_metadata_fieldnames,
                *self.regex.groupindex,
                *(f.name for f in fields(self.rule.ReplacementNotes)),
            ]
            writer = csv.DictWriter(csvfile, fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for change in self.text_changes:
                row = {
                    "original_text": change.match[0],
                    "replacement": change.replacement,
                    "has_changed": change.match[0] != change.replacement,
                    "replaced_on_site_name": change.content.website.name,
                    "replaced_on_site_short_id": change.content.website.short_id,
                    "replaced_on_page_uuid": change.content.text_id,
                    "replaced_on_page_url": get_rootrelative_url_from_content(
                        change.content
                    ),
                    **change.match.groupdict(),
                    **asdict(change.notes),
                }
                writer.writerow(row)
