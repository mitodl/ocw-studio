import json
from dataclasses import dataclass

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.link_grammar import (
    LinkParser,
)


class LinkLoggingRule(PyparsingRule):

    alias = "link_logging"

    fields = [
        'markdown',
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

    def __init__(self) -> None:
        super().__init__()
        self.parser = LinkParser()

    def replace_match(self, s: str, l: int, toks, website_content):
        link = toks.link
        notes = self.ReplacementNotes(
            text=link.text,
            destination=link.destination,
            title=json.dumps(link.title),
        )
        return toks.original_text, notes

    def should_parse(self, text: str):
        return '](' in text