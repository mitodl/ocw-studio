import json
from dataclasses import dataclass

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.shortcode_grammar import (
    ShortcodeParser,
)


class ShortcodeLoggingRule(PyparsingRule):

    alias = "shortcode_logging"

    Parser = ShortcodeParser
    @dataclass
    class ReplacementNotes:
        name: str
        num_args: int
        args: "list[str]"

    def replace_match(self, s: str, l: int, toks, website_content):
        shortcode = toks.shortcode
        notes = self.ReplacementNotes(
            name=shortcode.name,
            num_args=len(shortcode.args),
            args=json.dumps(shortcode.args),
        )
        return toks.original_text, notes
