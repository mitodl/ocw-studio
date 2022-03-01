"""
WebsiteContentMarkdownCleaner rule to convert

{{< resource_link 8c8f3d8e-da91-817b-219e-e6671b2456a6 "Link Text" >}}
to
{{% resource_link 8c8f3d8e-da91-817b-219e-e6671b2456a6 "Link Text" %}}
"""
import re

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
)
from websites.models import WebsiteContent


class ResourceLinkDelimitersReplacementRule(MarkdownCleanupRule):
    """Replacement rule for use with WebsiteContentMarkdownCleaner."""

    regex = r"{{<\sresource_link\s(?P<args>.*?)\s>}}"

    alias = "resource_link_delimiter_swap"

    def __call__(self, match: re.Match, website_content: WebsiteContent):
        args = match.group("args")
        return f"{{{{% resource_link {args} %}}}}"
