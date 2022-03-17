import json
from dataclasses import dataclass

from pyparsing import ParseResults, nestedExpr

from websites.management.commands.markdown_cleaning.parsing_utils import WrappedParser


@dataclass
class ShortcodeTag:
    """Represents a shortcode tag."""
    name: str
    args: "list[str]"
    percent_delimiters: bool = False
    closer: bool = False

    def get_delimiters(self):
        if self.percent_delimiters:
            opening_delimiter = "{{%"
            closing_delimiter = "%}}"
        else:
            opening_delimiter = "{{<"
            closing_delimiter = ">}}"

        if self.closer:
            opening_delimiter += "/"

        return opening_delimiter, closing_delimiter

    def to_hugo(self):
        """
        Encases all shortcode arguments in double quotes, because Hugo allows it and that's simplest.
        """
        opening_delimiter, closing_delimiter = self.get_delimiters()
        pieces = [
            opening_delimiter,
            self.name,
            *(self.hugo_escape(arg) for arg in self.args),
            closing_delimiter,
        ]
        return " ".join(pieces)

    @staticmethod
    def hugo_escape(s: str):
        return json.dumps(s)


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
        return s.strip('"').replace('\\"', '"')
