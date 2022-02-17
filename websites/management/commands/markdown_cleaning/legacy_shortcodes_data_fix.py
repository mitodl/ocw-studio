"""
These rules are intended to help fix data after the legacy shortocde incident.
Prior to https://github.com/mitodl/ocw-studio/pull/1013, "legacy" shortcodes
like {{< baseurl >}} would become corrupted in studio during editing. The editor:
    - displayed the shortcodes as raw text in studio edit
    - then escaped special characters like "[" and "<" when saving (only if edits were made)

This rule selectively unescapes content.
"""
import re

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
)


LINK_WITHOUT_IMAGE = r"\\\[[^\[\]]*\\\]\({{\\<"
LINK_WITH_IMAGE = r"\\\[!\\\[[^\[\]]*\][^\[\]]*\\\]\({{\\<"


class LegacyShortcodeFixOne(MarkdownCleanupRule):
    """
    Use this BEFORE LegacyShortcodeTwo because this matches against "{{\\<" for
    increased selectivity.
    """

    regex = f"{LINK_WITH_IMAGE}|{LINK_WITHOUT_IMAGE}"

    alias = "legacy_shortcode_datafix_1_of_2"

    def __call__(self, match: re.Match, _website_content):
        original_text = match[0]
        fixed = (
            original_text.replace("\\[", "[").replace("\\]", "]").replace("\\_", "_")
        )
        return fixed


class LegacyShortcodeFixTwo(MarkdownCleanupRule):
    """
    Use this AFTER LegacyShortcodeFixOne, which matches against the data fixed
    by this rule.
    """

    regex = r"{{\\< .*?>}}"

    alias = "legacy_shortcode_datafix_2_of_2"

    def __call__(self, match: re.Match, _website_content):
        original_text = match[0]
        fixed = original_text.replace("\\<", "<").replace("\\_", "_")
        return fixed
