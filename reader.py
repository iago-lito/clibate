from exceptions import SourceError


class Reader(object):
    """Readers are responsible to match partially consumed input
    and consume a bit of it to produce something meaningful.

    "Hard" readers are responsible for finding the end of their match,
    and hand out the remaining, unused input to the parser.

    "Soft" readers only indicate whether they match a start or not.
    When started, they are given the rest of the input line by line
    until another reader matches.
    """

    def match(self, input) -> "MatchResult" or None:
        """Check whether the input yields a start match."""
        raise NotImplementedError("Missing method 'match' for {type(self).__name__}.")


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

    pass
