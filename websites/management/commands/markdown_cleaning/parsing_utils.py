from pyparsing import originalTextFor, ParseResults

class WrappedParser:
    """
    Wrapper around Pyparsing grammars.

    This serves two purposes:
        1. Ensure availability of the original text for individual matches
            on parse actions.
        2. Provide nice snake_case names. Our version of Pyparsing does not have
            snake case names. (It's introduce in 3.0; we're on 2.4.7)
    """

    def __init__(self, grammar) -> None:

        self.grammar = originalTextFor(grammar)
        self.set_parse_action()


    @staticmethod
    def _original_text_for(s: str, _l: int, toks):
        original_text = s[toks.pop('_original_start'):toks.pop('_original_end')]
        results = toks.asDict()
        results['original_text'] = original_text
        return ParseResults.from_dict(results)

    def set_parse_action(self, *parse_actions):
        """
        Set parse actions to on the wrapped grammar. These will be called with
        arguments
            - s (str): the *entire* original string
            - l (int): starting index of match within s
            - toks (ParseResults): A ParseResults object with properties
                - original_text: the original text for *this* match
                - ...: and any named properties on parse results of the underlying
                    grammar.
        """
        self.grammar.setParseAction(self._original_text_for)
        self.grammar.addParseAction(*parse_actions)

    def parse_string(self, string: str):
        """
        Snake-case alias for PyParsing's parseString.
        """
        return self.grammar.parseString(string)

    def transform_string(self, string: str):
        """
        Snake-case alias for PyParsing's transformString
        """
        return self.grammar.transformString(string)
