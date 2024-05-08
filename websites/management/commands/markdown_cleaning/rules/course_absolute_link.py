"""
Rule to replaces relative course (root) links with absolute links.

For example, `courses/1-050-solid-mechanics-fall-2004` is replaced with
`/courses/1-050-solid-mechanics-fall-2004`.
"""
import re

from websites.management.commands.markdown_cleaning.cleanup_rule import (
    RegexpCleanupRule,
)
from websites.management.commands.markdown_cleaning.utils import ContentLookup

COURSE_LINK = r"\]\((courses\/[^\/\)]+)\/?\)"


class CourseAbsoluteLinkRule(RegexpCleanupRule):
    """
    This rule replaces relative course links with absolute course links.

    # Example

    Replaces the following

    ```
    courses/1-050-solid-mechanics-fall-2004
    ```

    with

    ```
    /courses/1-050-solid-mechanics-fall-2004
    ```

    This fixes a class of broken links caused by the use of
    relative links where absolute links are more appropriate.
    """

    regex = COURSE_LINK

    alias = "course_absolute_link"

    fields = [
        "markdown",
        "metadata.related_resources_text",
        "metadata.image_metadata.caption",
        "metadata.image_metadata.credit",
        "metadata.optional_text",
        "metadata.description",
        "metadata.course_description",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.content_lookup = ContentLookup()

    def _is_valid_course_url_path(self, url_path: str) -> str | None:
        """
        Return True if `url_path` is a valid.

        `url_path` is considered valid if it exists for a
        published course.
        """
        try:
            website_by_path = self.content_lookup.find_website_by_url_path(url_path)
        except KeyError:
            return False

        if website_by_path and website_by_path.unpublish_status is None:
            return True

        return False

    def replace_match(self, match: re.Match, _website_content):
        """
        See the docs for RegexpCleanupRule.replace_match.
        """
        if self._is_valid_course_url_path(match.group(1)):
            return f"](/{match.group(1)})"

        return match[0]
