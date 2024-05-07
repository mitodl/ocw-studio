import re

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.parsing_utils import ShortcodeTag
from websites.management.commands.markdown_cleaning.shortcode_parser import (
    ShortcodeParser,
    ShortcodeParseResult,
)
from websites.management.commands.markdown_cleaning.utils import remove_prefix


class ResourceLinkNextPrevRule(PyparsingRule):
    alias = "resource_link_nextprev"

    Parser = ShortcodeParser

    should_arse_regex = re.compile(r"\{\{%.*?%\}\}")

    @classmethod
    def should_parse(cls, text: str):
        """
        The `text` is only worth considering if it contains a resource link
        AND the resource link contains a > or <. Otherwise, skip it.
        """  # noqa: D401
        matches = cls.should_arse_regex.findall(text)
        return any("<" in m for m in matches) or any(">" in m for m in matches)

    def replace_match(
        self,
        s: str,  # noqa: ARG002
        l: int,  # noqa: ARG002, E741
        toks: ShortcodeParseResult,
        wc,  # noqa: ARG002
    ):
        shortcode = toks.shortcode
        original_text = toks.original_text

        if shortcode.name != "resource_link":
            return original_text

        link_text = shortcode.get(1)
        new_link_text = self.get_new_text(link_text)
        if link_text == new_link_text:
            return original_text

        new_shortcode = ShortcodeTag.resource_link(
            uuid=shortcode.get(0), text=new_link_text, fragment=shortcode.get(2)
        )

        return new_shortcode.to_hugo()

    @staticmethod
    def get_new_text(text: str):
        prevs = [R"\<\<", R"\<"]
        nexts = [R"\>\>", R"\>"]
        for p in prevs:
            if text.startswith(p):
                return "« " + remove_prefix(text, p).lstrip()
        for n in nexts:
            if text.startswith(n):
                return "» " + remove_prefix(text, n).lstrip()
        return text
