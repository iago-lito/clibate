from exceptions import ParseError, LineFeedError


class Parser(object):
    """Responsible for coordinating all the read modules together.
    And parse one string into a list of readers results.
    """

    def __init__(self, specs, readers, filename=None):
        """Initialize from a string and a set of readers."""

        # Keep a copy of the whole specifications.
        self.specs = specs  # (remains constant)
        self.readers = readers
        self.filename = filename

        # The parser is consumed when all input is consumed.
        self.input = specs  # (consumed as parsing goes)

        # Keep track of position within the file.
        self.linenum = 1
        self.colnum = 1

    @property
    def position(self):
        "Construct a string identifying current position within the parsed string."
        res = f"line {self.linenum} column {self.colnum}"
        if self.filename is not None:
            res += f" in {self.filename}"
        return res

    def find_matching_reader(self) -> "MatchResult" or None:
        """Consume necessary input for one reader to match at current position."""

        input = self.input

        # Error out if several readers match: ambiguity.
        matches = []  # [(match_result, reader)]
        for reader in self.readers:
            if m := reader.match(input):
                matches.append((m, reader))
        if len(matches) > 1:
            readers = [type(r).__name__ for _, r in matches]
            if len(readers) == 2:
                readers = "both readers " + " and ".join(readers)
            else:
                readers = (
                    "all readers " + ", ".join(readers[:-1]) + " and " + readers[-1]
                )
            raise ParseError(
                f"Ambiguity in parsing: {readers} match at {self.position}."
            )
        # It may be that none matched.
        if len(matches) == 0:
            return None

        [(match, reader)] = matches

        # Consume utilized input (updating position).
        used, remaining = input[: match.end], input[match.end :]
        newlines = used.count("\n")
        self.linenum += newlines
        if newlines:
            self.colnum = len(used.rsplit("\n", 1)[1]) + 1
        self.input = remaining

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
                raise ParseError(f"No readers matching input ({self.position}).")

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
                    collect.append(automaton.terminate())
                    match = None
                    break
                match = self.find_matching_reader()
                if not match:
                    # Extract current line and process it.
                    line, remaining = self.input.split("\n", 1)
                    try:
                        automaton.feed(line)
                    except LineFeedError as e:
                        raise ParseError(
                            "Automaton failed on the following line:\n"
                            f"--> {line}\n({self.position})"
                        ) from e
                    self.input = remaining
                    self.linenum += 1
                    self.colnum = 1
                    continue
                # In case of match, the automaton should be done.
                collect.append(automaton.terminate())
                break
            if not match and not self.input:
                break

        # All input has been parsed.
        return collect
