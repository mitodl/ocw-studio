from dataclasses import dataclass
import json
from websites.management.commands.markdown_cleaning.cleanup_rule import (
    PyparsingRule
)
from websites.management.commands.markdown_cleaning.shortcode_grammar import (
    ShortcodeParser,
    ShortcodeTag
)

class RemoveExtraResourceArgs(PyparsingRule):

    alias = 'remove_extra_resource_args'

    def should_parse(self, text: str):
        return R'{{< resource ' in text

    @dataclass
    class ReplacementNotes:
        name: str
        num_args: int
        args: 'list[str]'

    def __init__(self) -> None:
        super().__init__()
        self.parser = ShortcodeParser()

    def replace_match(self, s: str, l: int, toks, website_content):
        shortcode: ShortcodeTag = toks.shortcode
        notes = self.ReplacementNotes(name=shortcode.name, num_args=len(shortcode.args), args=json.dumps(shortcode.args))
        
        if shortcode.name != 'resource' or len(shortcode.args) == 1:
            return toks.original_text, notes
        
        replacement = ShortcodeTag(
            name=shortcode.name,
            args=[shortcode.args[0]],
            closer=shortcode.closer,
            percent_delimiters=shortcode.percent_delimiters
        )
        return replacement.to_hugo(), notes