from exceptions import ParseError, NoSectionMatch
from lexer import Lexer
from sections import default_readers

from pathlib import Path


class ParseContext(object):
    """Useful aggregate to pass parsing position around,
    but also more general context like original file,
    the set of readers used to parse input (within the parser itself),
    or the chain of included files leading to this being parsed.
    """

    # TODO: The context flows from parsing to readers to actors/checkers to the test_set
    # and eventually back to the parser when files are `include:`d from one another,
    # but the flow is not fully exploited yet because readers and lines automata
    # possibly spawn their own lexers, starting from 0, and because keeping a ref to the
    # context for constructing a possible later message reference
    # does not keep it from being consumed meanwhile.
    # On the other hand, the context cannot be messed with because consuming it wrong
    # invalidates all subsequent parsing.
    # Maybe the parsing context could be more pervasive,
    # yet more hidden/protected/documented,
    # consumed only by the `Parser`, the parent class `Reader`,
    # and by subclasses really knowing what they do.
    # It could also be easier to spawn it and, for instance, passing a protected fork of
    # it with only one line left to consume to the lines automata..

    def __init__(
        self, input, parser, filename=None, file_path=None, include_chain=None
    ):
        self.input = input
        self.parser = parser
        self.filename = filename  # As entered by user at some point.
        self.file_path = file_path  # Canonically resolved.
        self.n_consumed = 0
        self.linenum = 1
        self.colnum = 1
        # [(included file (full path), including_position (entered name))]
        self.include_chain = include_chain if include_chain is not None else []

    @property
    def position(self) -> str:
        "Construct a string identifying current position within the parsed string."
        fn = self.filename if self.filename is not None else "<None>"
        res = f"{fn}:{self.linenum}:{self.colnum}"
        return res

    @property
    def consumed(self):
        """True if there is no input left."""
        return not self.input

    def consume(self, n_consumed):
        """Update self.input and calculate new linenum/colnum based on remaining input
        and number of chars consumed.
        """
        consumed, remaining = self.input[:n_consumed], self.input[n_consumed:]
        self.n_consumed += n_consumed
        newlines = consumed.count("\n")
        self.linenum += newlines
        if newlines:
            self.colnum = len(consumed) - consumed.rfind("\n")
        else:
            self.colnum += len(consumed)
        self.input = remaining


class Parser(object):
    """Responsible for coordinating all the read modules together.
    And parse one string into a list of readers results.
    """

    def __init__(self, readers):
        self.readers = readers

        # Keep track of position within the file.
        # The parser is consumed when all input in context is consumed.
        self.context = None  # (set before parsing, passed to readers)

    def reraise(self, parse_error):
        """Consume input until error, append position information
        then forward the error up.
        """
        self.context.consume(parse_error.n_consumed)
        raise ParseError(
            parse_error.message + f" ({self.context.position})"
        ) from parse_error

    def find_matching_reader(self) -> "MatchResult" or None:
        """Consume necessary input for one reader to match at current position."""

        context = self.context

        # Error out if several readers match: ambiguity.
        matches = []  # [(match_result, reader)]
        for reader in self.readers:
            try:
                if m := reader.match(context.input, self.context):
                    matches.append((m, reader))
            except NoSectionMatch:
                pass
            except ParseError as e:
                self.reraise(e)
        if len(matches) > 1:
            readers = [type(r).__name__ for _, r in matches]
            if len(readers) == 2:
                readers = "both readers " + " and ".join(readers)
            else:
                readers = (
                    "all readers " + ", ".join(readers[:-1]) + " and " + readers[-1]
                )
            raise ParseError(
                f"Ambiguity in parsing: {readers} match at {self.context.position}."
            )
        # It may be that none matched.
        if len(matches) == 0:
            return None

        [(match, reader)] = matches

        # Consume utilized input (updating position).
        context.consume(match.end)

        return match

    def parse(self, context):
        """Iteratively hand the input to readers
        so they consume it bit by bit.
        """

        self.context = context

        # One iteration, one collected object.
        collect = []
        match = None  # Currently being processed.
        while True:

            if not match:
                match = self.find_matching_reader()

            if not match:
                l = Lexer(context.input)
                if l.find_empty_line():
                    # It's okay that we have not matched on an empty line
                    # or a pure comment. Consume and move on.
                    context.consume(l.n_consumed)
                    if context.consumed:
                        break
                    matching_started = False
                    continue
                raise ParseError(
                    f"No readers matching input ({self.context.position})."
                )

            if match.type == "hard":
                # The reader has already produced a valid object.
                collect.append(match.parsed)
                if context.consumed:
                    break
                match = None
                continue

            # Otherwise, it has returned an automaton
            # that we need to feed with lines until another reader matches.
            automaton = match.lines_automaton
            while True:
                if context.consumed:
                    try:
                        collect.append(automaton.terminate())
                    except ParseError as e:
                        self.reraise(e)
                    match = None
                    break
                # Save in case a parse error occurs during termination of current soft.
                pos = self.context.position
                match = self.find_matching_reader()
                if not match:
                    # Extract current line and process it.
                    line, remaining = context.input.split("\n", 1)
                    try:
                        automaton.feed(line, self.context)
                    except ParseError as e:
                        self.reraise(e)
                    context.consume(len(line) + 1)
                    continue
                # In case of match, the automaton should be done.
                try:
                    collect.append(automaton.terminate())
                except ParseError as e:
                    raise ParseError(e.message + f" ({pos})") from e
                break
            if not match and context.consumed:
                break

        # All input has been parsed.
        return collect

    @staticmethod
    def parse_file(
        filename, file_path=None, readers=None, include_chain=None
    ) -> [object]:
        """Construct a parser to read and parse given file,
        producing a sequence of parsed objects resulting from the various readers.
        """
        # Construct parser.
        if readers is None:
            readers = default_readers()
        parser = Parser(readers)

        # Retrieve input, setup context.
        if not file_path:
            file_path = Path(filename).resolve()
        with open(file_path, "r") as file:
            input = file.read()
        if include_chain is None:
            include_chain = [(file_path, "<root>")]
        context = ParseContext(input, parser, filename, file_path, include_chain)

        # Do the job.
        return parser.parse(context)
