import re

from websites.management.commands.markdown_cleaning.cleanup_rule import PyparsingRule
from websites.management.commands.markdown_cleaning.parsing_utils import (
    ShortcodeParam,
    ShortcodeTag,
)
from websites.management.commands.markdown_cleaning.shortcode_parser import (
    ShortcodeParser,
    ShortcodeParseResult,
)


class SubSupFixes(PyparsingRule):
    """
    This fixes two issues with {{< sub >}} and {{< sup >}} shortcodes

    - leading +/- need to be escaped in the subscript/superscript values because
    we call markdownify on these values. If they are both leading AND unescaped,
    markdownify treats them as list bullets

    Do auto-escape leading *. There aren't very many, and most of the time they
    seem to be intended as bold/italics.

    - a bunch of +/-/* got extra escapes, probably from before CKEditor was
    updated to handle "legacy" shortcodes.
    """

    alias = "subsup"

    Parser = ShortcodeParser

    def should_parse(self, s: str):
        variants = [R"{{< sub", R"{{< sup"]
        return any(v in s for v in variants)

    def replace_match(
        self, s: str, l: int, toks: ShortcodeParseResult, wc  # noqa: ARG002, E741
    ):  # noqa: E741, RUF100
        shortcode = toks.shortcode
        original_text = toks.original_text
        if shortcode.name not in ["sub", "sup"]:
            return original_text

        old_param = shortcode.get(0)
        new_param = self.get_new_subsup_value(old_param)

        if new_param == old_param:
            return original_text

        new_shortcode = ShortcodeTag(
            name=shortcode.name,
            percent_delimiters=shortcode.percent_delimiters,
            params=[ShortcodeParam(new_param)],
            closer=shortcode.closer,
        )
        return new_shortcode.to_hugo()

    @staticmethod
    def get_new_subsup_value(text: str):
        """
        Get the new value for text in a subscript / superscript.
        """

        escaped_bullet = re.compile(r"\\\\(?P<bullet>[\-\+\*])")

        def replacer(match: re.Match):
            return f'\\{match.group("bullet")}'

        new_text = escaped_bullet.sub(replacer, text)

        # escape leading +/- because markdown interprets them as lists.
        # But do NOT escape leading * because almost always it's part of italics/bold.
        # Handle leading * manually if we need to. There are only 2 or 3.
        bullets = ["-", "+"]
        if any(new_text.startswith(b) for b in bullets):
            new_text = "\\" + new_text

        return new_text
