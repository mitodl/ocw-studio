"""
These rules are intended to help fix data after the legacy shortocde incident.
Prior to https://github.com/mitodl/ocw-studio/pull/1013, "legacy" shortcodes
like {{< baseurl >}} would become corrupted in studio during editing. The editor:
    - displayed the shortcodes as raw text in studio edit
    - then escaped special characters like "[" and "<" when saving (only if edits were made)

This rule selectively unescapes content.

### Strategy
In general, there there are two data corruptions we're trying to fix. Consider
the texts

    blah \[Some Tile\]{{\< resource\_file uuid >}} blah
    blah blah {{\< sup 2 >}} blah

We will make two rules:
1. Fix the stuff BEFORE the shortcode, namely link/image title (line 1)
2. Fix the shortcode itself and its contents

The `\<` in the first line will be caught by the second rule.
"""
import re

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    RegexpCleanupRule,
)


LINK_WITHOUT_IMAGE = r"\\\[[^\[\]]*\\\]\({{\\<"
LINK_WITH_IMAGE = r"\\\[!\\\[[^\[\]]*\][^\[\]]*\\\]\({{\\<"


class LegacyShortcodeFixOne(RegexpCleanupRule):
    """
    Use this BEFORE LegacyShortcodeTwo because this matches against "{{\\<" for
    increased selectivity.
    """

    regex = f"{LINK_WITH_IMAGE}|{LINK_WITHOUT_IMAGE}"

    alias = "legacy_shortcode_datafix_1_of_2"

    def replace_match(self, match: re.Match, _website_content):
        original_text = match[0]
        # Intentially not converting {{\< to {{< ... that will be fixed by Rule Two
        fixed = (
            original_text.replace("\\[", "[").replace("\\]", "]").replace("\\_", "_")
        )
        return fixed
