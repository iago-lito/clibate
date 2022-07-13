from exceptions import SourceError, NoSectionMatch
from lexer import Lexer


class Reader(object):
    """Readers are responsible to match partially consumed input
    and consume a bit of it to produce something meaningful.

    "Hard" readers are responsible for finding the end of their match,
    and hand out the remaining, unused input to the parser.

    "Soft" readers only indicate whether they match a start or not.
    When started, they are given the rest of the input line by line
    until another reader matches.

    As the parent class of all readers,
    Reader offers a Lexer-wrapping API for basic parsing of the input given in match.
    So, although in principle every subtype may rewrite everything
    and parse the spec file the way it wants,
    there are facilities to read clibate sections with a typical-look.
    """

    def match(self, input) -> "MatchResult" or None:
        """Check whether the input yields a start match."""
        raise NotImplementedError("Missing method 'match' for {type(self).__name__}.")

    def section_name(self):
        """Infer section name, assuming the reader's name is <SectionName>Reader."""
        return type(self).__name__.removesuffix("Reader")

    def define_lexer(self, input):
        """Entry point into the Reader's API:
        defines and attaches a Lexer instance to self,
        so future calls don't need to pass it always as an argument.
        """
        self.lexer = Lexer(input)

    def check_keyword(self):
        """Check that the reader's `self.keyword` is starting the match,
        Otherwise warn the calling parser with the correct exception.
        """
        if not self.lexer.match(self.keyword):
            raise NoSectionMatch()

    def introduce(self, input):
        """Common entrypoint both spawning the lexer and checking section keyword."""
        self.define_lexer(input)
        self.check_keyword()

    def check_colon(self):
        """Check that the section is correctly introduced by a colon ':'."""
        lex = self.lexer
        if not lex.find(":"):
            lex.error(f"Missing colon ':' to introduce {self.section_name()} section.")

    def soft_match(self, automaton):
        """Produce a correct soft matching result based on lexing done so far."""
        return MatchResult(
            type="soft",
            lines_automaton=automaton,
            end=self.lexer.n_consumed,
        )


class MatchResult(object):
    "Gather all information related to a positive match result."

    valid_types = ("soft", "hard")

    def __init__(self, type=None, end=None, parsed=None, lines_automaton=None):
        # Position of the end of match in given input.
        if not end:
            raise SourceError("Match results must specify where they end.")
        self.end = end
        if type not in self.valid_types:
            valid = " ".join(f"'{t}'" for t in self.valid_types)
            raise SourceError(
                f"Invalid reader match type: '{type}'. Valid types: {valid}."
            )
        self.type = type
        # Resulting object in case of hard matching.
        if type == "hard" and not parsed:
            raise SourceError(
                f"Hard matching result should be provided a parsed object."
            )
        self.parsed = parsed
        # Automaton to construct next objects in case of soft matching.
        self.lines_automaton = lines_automaton
        if type == "soft" and not lines_automaton:
            raise SourceError(
                f"Soft matching result should be provided a lines automaton."
            )


class LinesAutomaton(object):
    """Lines automaton are returned by soft matching readers
    to process successive lines into a progressively constructed object
    until another reader starts matching.
    """

    def feed(self, line):
        """Process one line and keep constructing the object from it.
        Raise LineFeedError in case processing failed.
        """
        raise NotImplementedError("Missing method 'feed' for {type(self).__name__}.")

    def terminate(self):
        """Signal that all lines have been fed.
        Finish constructing the object and return it.
        """
        raise NotImplementedError(
            "Missing method 'terminate' for {type(self).__name__}."
        )
