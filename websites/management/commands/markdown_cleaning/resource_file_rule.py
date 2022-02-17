"""
WebsiteContentMarkdownCleaner rule to convert

![link alt text]({{< resource_file 8c8f3d8e-da91-817b-219e-e6671b2456a6 >}})
to 
{{< resource 8c8f3d8e-da91-817b-219e-e6671b2456a6 >}}

The link's custom alt text will be lost, instead depending on the resource's
metadata for alt text.
"""
import re

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    MarkdownCleanupRule,
)
from websites.models import WebsiteContent


class ResourceFileReplacementRule(MarkdownCleanupRule):
    """Replacement rule for use with WebsiteContentMarkdownCleaner."""

    regex = r"!\[(?P<alt_text>[^\[\]]*)\]\({{< resource_file\s(?P<resource_uuid>[a-z0-9\-]*)\s>}}\)"

    alias = "resource_file_to_resource"

    def __call__(self, match: re.Match, website_content: WebsiteContent):
        escaped_title = match.group("resource_uuid")
        return f"{{{{< resource {escaped_title} >}}}}"
