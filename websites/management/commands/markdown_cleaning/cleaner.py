"""Facilitates regex-based replacements on WebsiteContentMarkdown."""
import csv
import re
from collections import namedtuple

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
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

    ReplacementMatch = namedtuple(
        "ReplacementMatch",
        ["match", "replacement", "website_content_uuid", "website_uuid"],
    )
    csv_metadata_fieldnames = [
        "original_text",
        "replacement",
        "website_content_uuid",
        "website_uuid",
    ]

    def __init__(self, rule: MarkdownCleanupRule):
        self.regex = self.compile_regex(rule.regex)

        self.text_changes: "list[WebsiteContentMarkdownCleaner.ReplacementMatch]" = []
        self.updated_website_contents: "list[WebsiteContent]" = []
        self.updated_sync_states: "list[ContentSyncState]" = []

        def _replacer(match: re.Match, website_content: WebsiteContent):
            replacement = rule(match, website_content)
            self.text_changes.append(
                self.ReplacementMatch(
                    match,
                    replacement,
                    website_content.text_id,
                    website_content.website_id,
                )
            )
            return replacement

        self.replacer = _replacer

    def update_website_content_markdown(self, website_content: WebsiteContent):
        """
        Updates website_content's markdown in-place. Does not commit to
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

    def update_website_content_checksum(self, website_content: WebsiteContent):
        """
        Updates website_content's sync state checksum in-place. Does not commit to database.
        """
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
            fieldnames = [*self.csv_metadata_fieldnames, *self.regex.groupindex]
            writer = csv.DictWriter(csvfile, fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for change in self.text_changes:
                row = {
                    "website_content_uuid": change.website_content_uuid,
                    "website_uuid": change.website_uuid,
                    "original_text": change.match[0],
                    "replacement": change.replacement,
                    **change.match.groupdict(),
                }
                writer.writerow(row)
