import json
from dataclasses import asdict, dataclass

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.shortcode_parser import (
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

    def replace_match(
        self,
        s: str,  # noqa: ARG002
        l: int,  # noqa: ARG002, E741
        toks,
        website_content,  # noqa: ARG002
    ):
        shortcode = toks.shortcode
        notes = self.ReplacementNotes(
            name=shortcode.name,
            num_args=len(shortcode.params),
            args=json.dumps([asdict(p) for p in shortcode.params]),
        )
        return toks.original_text, notes
