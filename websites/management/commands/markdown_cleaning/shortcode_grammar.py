from pyparsing import ParseResults, nestedExpr

from websites.management.commands.markdown_cleaning.parsing_utils import (
    ShortcodeTag,
    WrappedParser,
    unescape_quoted_string
)


class ShortcodeParser(WrappedParser):
    def __init__(self):
        def record_shortcode(percent_delimiters: bool):
            """
            Returns a pyparsing parse action that transforms the nestedExpr
            match into a ParsedShortcode object.
            """

            def _parse_action(s: str, l: int, toks: "list[list[str]]"):
                if len(toks) > 1:
                    raise ValueError("Assumption violated. Investigate.")
                if any(not isinstance(s, str) for s in toks[0]):
                    raise ValueError("Unexpected shortcode nesting.")
                is_closing_tag = toks[0][0] == "/"
                content = toks[0][1:] if is_closing_tag else toks[0]
                name = content[0]
                args = [self.hugo_unescape_shortcode_arg(s) for s in content[1:]]
                shortcode = ShortcodeTag(
                    name, args, percent_delimiters, closer=is_closing_tag
                )
                return ParseResults.from_dict({"shortcode": shortcode})

            return _parse_action

        angle_expr = nestedExpr(opener=R"{{<", closer=R">}}").setParseAction(
            record_shortcode(percent_delimiters=False)
        )
        percent_expr = nestedExpr(opener=R"{{%", closer=R"%}}").setParseAction(
            record_shortcode(percent_delimiters=True)
        )

        grammar = angle_expr | percent_expr
        super().__init__(grammar)

    @staticmethod
    def hugo_unescape_shortcode_arg(s: str):
        quoted = '"' + s.strip('"') + '"'
        return unescape_quoted_string(quoted)
