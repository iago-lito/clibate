from exceptions import ParseError, NoSectionMatch
from lexer import Lexer


class ParseContext(object):
    """Useful aggregate to pass parsing position around."""

    def __init__(self, filename, linenum, colnum):
        self.filename = filename
        self.linenum = linenum
        self.colnum = colnum

    @property
    def position(self):
        "Construct a string identifying current position within the parsed string."
        fn = self.filename if self.filename is not None else "<None>"
        res = f"{fn}:{self.linenum}:{self.colnum}"
        return res


class Parser(object):
    """Responsible for coordinating all the read modules together.
    And parse one string into a list of readers results.
    """

    def __init__(self, specs, readers, filename=None):
        """Initialize from a string and a set of readers."""

        # Keep a copy of the whole specifications.
        self.specs = specs  # (remains constant)
        self.readers = readers

        # The parser is consumed when all input is consumed.
        self.input = specs  # (consumed as parsing goes)

        # Keep track of position within the file.
        self.context = ParseContext(filename, 1, 1)

    def consume(self, n_consumed):
        """Update self.input and calculate new linenum/colnum based on remaining input
        and number of chars consumed.
        """
        consumed, remaining = self.input[:n_consumed], self.input[n_consumed:]
        newlines = consumed.count("\n")
        self.context.linenum += newlines
        if newlines:
            self.context.colnum = len(consumed) - consumed.rfind("\n")
        else:
            self.context.colnum += len(consumed)
        self.input = remaining

    def reraise(self, parse_error):
        """Consume input until error, append position information
        then forward the error up.
        """
        self.consume(parse_error.n_consumed)
        raise ParseError(
            parse_error.message + f" ({self.context.position})"
        ) from parse_error

    def find_matching_reader(self) -> "MatchResult" or None:
        """Consume necessary input for one reader to match at current position."""

        input = self.input

        # Error out if several readers match: ambiguity.
        matches = []  # [(match_result, reader)]
        for reader in self.readers:
            try:
                if m := reader.match(input, self.context):
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
        self.consume(match.end)

        return match

    def parse(self):
        """Iteratively hand the input to readers
        so they consume it bit by bit.
        """

        # One iteration, one collected object.
        collect = []
        match = None  # Currently being processed.
        while True:

            if not match:
                match = self.find_matching_reader()

            if not match:
                l = Lexer(self.input)
                if l.find_empty_line():
                    # It's okay that we have not matched on an empty line
                    # or a pure comment. Consume and move on.
                    self.consume(l.n_consumed)
                    if not self.input:
                        break
                    matching_started = False
                    continue
                raise ParseError(
                    f"No readers matching input ({self.context.position})."
                )

            if match.type == "hard":
                # The reader has already produced a valid object.
                collect.append(match.parsed)
                if not self.input:
                    # Consumed!
                    break
                match = None
                continue

            # Otherwise, it has returned an automaton
            # that we need to feed with lines until another reader matches.
            automaton = match.lines_automaton
            while True:
                if not self.input:
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
                    line, remaining = self.input.split("\n", 1)
                    try:
                        automaton.feed(line, self.context)
                    except ParseError as e:
                        self.reraise(e)
                    self.input = remaining
                    self.context.linenum += 1
                    self.context.colnum = 1
                    continue
                # In case of match, the automaton should be done.
                try:
                    collect.append(automaton.terminate())
                except ParseError as e:
                    raise ParseError(e.message + f" ({pos})") from e
                break
            if not match and not self.input:
                break

        # All input has been parsed.
        return collect
