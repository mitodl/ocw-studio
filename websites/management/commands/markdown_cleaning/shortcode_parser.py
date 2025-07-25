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
        def record_shortcode(percent_delimiters: bool):  # noqa: FBT001
            """
            Returns a pyparsing parse action that transforms the nestedExpr
            match into a ParsedShortcode object.
            """  # noqa: D401

            def _parse_action(
                s: str,  # noqa: ARG001
                l: int,  # noqa: ARG001, E741
                toks: "list[list[str]]",
            ):
                if len(toks) > 1:
                    msg = "Assumption violated. Investigate."
                    raise ValueError(msg)
                if any(not isinstance(s, str) for s in toks[0]):
                    msg = "Unexpected shortcode nesting."
                    raise ValueError(msg)
                is_closing_tag = toks[0][0] == "/"
                content = toks[0][1:] if is_closing_tag else toks[0]
                name = content[0]
                param_assignments: list[str] = []
                for part in content[1:]:
                    if param_assignments and param_assignments[-1].endswith("="):
                        param_assignments[-1] += part
                    else:
                        param_assignments.append(part)

                params = [ShortcodeParam.from_hugo(s) for s in param_assignments]
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
