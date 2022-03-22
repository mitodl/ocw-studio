from dataclasses import dataclass

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.link_grammar import LinkParser


class LinkLoggingRule(PyparsingRule):
    """
    Find all links in all Websitecontent markdown bodies plus some metadata
    fields and log information about them to a csv.

    Never changes stuff.
    """

    alias = "link_logging"

    Parser = LinkParser

    fields = [
        "markdown",
        "metadata.related_resources_text",
        "metadata.image_metadata.caption",
        "metadata.image_metadata.credit",
        "metadata.optional_text",
        "metadata.description",
        "metadata.course_description",
    ]

    @dataclass
    class ReplacementNotes:
        text: str
        destination: str
        title: str

    def replace_match(self, s: str, l: int, toks, website_content):
        link = toks.link
        notes = self.ReplacementNotes(
            text=link.text,
            destination=link.destination,
            title=link.title,
        )
        return toks.original_text, notes

    def should_parse(self, text: str):
        """Should the text be parsed?

        If the text does not contain '](', then it definitely does not have
        markdown links.
        """
        return "](" in text
