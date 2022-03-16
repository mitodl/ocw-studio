from dataclasses import dataclass
import json
from websites.management.commands.markdown_cleaning.cleanup_rule import (
    PyparsingRule
)
from websites.management.commands.markdown_cleaning.shortcode_grammar import (
    ShortcodeParser
)

class ShortcodeLoggingRule(PyparsingRule):

    alias = 'shortcode_logging'

    @dataclass
    class ReplacementNotes:
        name: str
        num_args: int
        args: 'list[str]'

    def __init__(self) -> None:
        super().__init__()
        self.parser = ShortcodeParser()

    def replace_match(self, s: str, l: int, toks, website_content):
        shortcode = toks.shortcode
        notes = self.ReplacementNotes(name=shortcode.name, num_args=len(shortcode.args), args=json.dumps(shortcode.args))
        return shortcode.to_hugo(), notes