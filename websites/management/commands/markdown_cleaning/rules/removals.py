from websites.management.commands.markdown_cleaning.cleanup_rule import (
    RegexpCleanupRule,
)


class RemoveInaccesibleGifRule(RegexpCleanupRule):
    """
    Remove all instances of "![This resource may not render correctly in a screen reader.](/images/inacessible.gif)".
    """

    alias = "inaccessible"

    # Yes, literally this. Period.
    # Helpfully, inacessible is mispelled which makes it even more specific!.
    regex = r"!\[This resource may not render correctly in a screen reader\.\]\(/images/inacessible\.gif\)"

    fields = ["markdown", "metadata.optional_text", "metadata.related_resources_text"]

    def replace_match(self, match, website_content) -> str:
        return ""
