from context import ContextLexer
from exceptions import ParseError, SourceError, NoSectionMatch

from types import MethodType


class Reader(object):
    """Readers are responsible to match one particular section of the file,
    given a contextualized lexer handed to them by the main parser.
    They are free to consume it, but must not consume more than they need,
    because their version of the lexer is eventually offered to subsequent readers
    if they match.

    "Hard" readers ar able to directly find the end of their match,
    and need not be called back.

    "Soft" readers recognize that their section started,
    but the end of their match is actually the beginning of another reader's match,
    so they can't exactly tell.
    Instead of returning a fully parsed object like Actor or Checker,
    they return a LinesAutomaton to the main parser.
    The parser will feed this automaton with subsequent input, *line by line*,
    until another reader matches and takes over.
    The automaton then `.terminate()`s to produce the actual, fully parsed object.

    Note that readers behave as 'hard' or 'soft' depending on the actual input.

    As the parent class of all readers,
    Reader offers a Lexer-wrapping API for basic parsing of the input given in match.
    So, although in principle every subtype may rewrite everything
    and parse the spec file the way it wants,
    there are facilities to read clibate sections with a typical-look.

    Most basic lexing utilities are implemented in the base lexer,
    here are more high-level pre-defined lexing operations to match clib look.
    """

    def section_match(self, lexer) -> object or None:
        """Check whether the input yields a start match."""
        raise NotImplementedError("Missing method 'match' for {type(self).__name__}.")

    def section_name(self):
        """Infer section name, assuming the reader's name is <SectionName>Reader."""
        return type(self).__name__.removesuffix("Reader")

    def attach_lexer(self, lex):
        """Entry point into the Reader's API:
        attaches the instance to self,
        so future calls don't need to pass it as an explicit argument.
        """
        self.lexer = lex

    def check_keyword(self):
        """Check that the reader's `self.keyword` is starting the match,
        Otherwise warn the calling parser with the correct exception.
        Sets `self.keyword_context` for future reference, as part of the API.
        """
        if not hasattr(self, "keyword"):
            raise SourceError(f"No 'self.keyword' defined for {type(self).__name__}.")
        lex = self.lexer
        context = lex.context
        if not lex.match(self.keyword):
            raise NoSectionMatch()
        self.keyword_context = context

    def introduce(self, lex):
        """Common entrypoint both spawning the lexer and checking section keyword."""
        self.attach_lexer(lex)
        self.check_keyword()

    def check_colon(self):
        """Check that the section is correctly introduced by a colon ':'."""
        lex = self.lexer
        if not lex.find(":"):
            lex.error(f"Missing colon ':' to introduce {self.section_name()} section.")

    def check_double_colon(self):
        """Check that the section is correctly introduced by two colons '::'."""
        lex = self.lexer
        if not lex.find("::"):
            lex.error(
                "Missing double colon '::' "
                f"to introduce {self.section_name()} section."
            )

    def check_colon_type(self) -> (":" or "::"):
        """Check wether the section is introduced
        by a colon ':' (to spot soft-matchers)
        or a double colon '::' (to spot hard-matchers),
        Errors out otherwise."""
        try:
            self.check_double_colon()
            return "::"
        except ParseError:
            pass
        try:
            self.check_colon()
            return ":"
        except ParseError:
            pass
        self.lexer.error(
            "Missing colon ':' (soft-matching) or double colon '::' (hard-matching) "
            f"to introduce {self.section_name()} section."
        )

    # Defer basic calls to Lexer's API.
    def __getattr__(self, name):
        """Defer basic calls to Lexer's API, provided they conform "
        to the passlist defined by ContextLexer."""
        if name in ContextLexer._lexer_defer:
            method = getattr(ContextLexer, name)
            return MethodType(method, self.lexer)
        raise AttributeError(
            f"{type(self).__name__} has no attribute '{name}', "
            f"and '{name}' is not a method defered to the Lexer."
        )


class LinesAutomaton(object):
    """Lines automaton are returned by soft matching readers
    to process successive lines into a progressively constructed object,
    and until another reader starts matching.
    """

    def feed(self, lexer):
        """Process one line and keep constructing the object from it.
        Raise LineFeedError in case processing failed.
        The lexer received will EOI at the end of the line.
        """
        raise NotImplementedError("Missing method 'feed' for {type(self).__name__}.")

    def terminate(self):
        """That's the signal, send to us by the main parser,
        that all lines have been fed.
        Finish constructing the object and return it.
        """
        raise NotImplementedError(
            "Missing method 'terminate' for {type(self).__name__}."
        )
