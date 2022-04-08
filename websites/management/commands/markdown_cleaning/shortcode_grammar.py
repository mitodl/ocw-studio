from typing import Protocol

from pyparsing import ParseResults, nestedExpr

from websites.management.commands.markdown_cleaning.parsing_utils import (
    ShortcodeParam,
    ShortcodeTag,
    WrappedParser,
)


class ShortcodeParseResult(Protocol):

    shortcode: ShortcodeTag
    original_text: str


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
                param_assignments: list[str] = []
                for s in content[1:]:
                    if param_assignments and param_assignments[-1].endswith("="):
                        param_assignments[-1] += s
                    else:
                        param_assignments.append(s)

                try:
                    params = [ShortcodeParam.from_hugo(s) for s in param_assignments]
                except ValueError:
                    params = [ShortcodeParam("UNKNOWN")]
                shortcode = ShortcodeTag(
                    name, params, percent_delimiters, closer=is_closing_tag
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
