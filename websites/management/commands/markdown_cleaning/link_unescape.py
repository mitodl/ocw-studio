"""
Markdown links in Studio can be erroneously escaped, e.g.,
    \[ link text \](link url)
This happens particularly with links containing baseurl:
    1. Markdown contains [link text]({{ < baseurl > }}/path/to/thing)
    2. user edits and save
    3 link is escaped \[link text\]({{ < baseurl > }}/path/to/thing) because
        showdown does not recognize the markdown, since the "link" contains
        spaces in its destination, which CommonMark does not allow.
"""
import re

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    RegexpCleanupRule,
)


LINK_WITHOUT_IMAGE = r"\\\[[^\[\]]*\\\]\({{<"
LINK_WITH_IMAGE = r"\\\[!\\\[[^\[\]]*\][^\[\]]*\\\]\({{<"


class LinkUnescape(RegexpCleanupRule):
    """
    Unescape links that have been escaped accidentally.
    """

    regex = f"{LINK_WITH_IMAGE}|{LINK_WITHOUT_IMAGE}"

    alias = "link_unescape"

    def replace_match(self, match: re.Match, _website_content):
        original_text = match[0]
        # Intentially not converting {{\< to {{< ... that will be fixed by Rule Two
        fixed = (
            original_text.replace("\\[", "[").replace("\\]", "]").replace("\\_", "_")
        )
        return fixed
