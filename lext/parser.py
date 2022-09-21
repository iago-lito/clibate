from .context import ParseContext, ContextLexer, EOI
from .exceptions import ParseError, NoSectionMatch
from .parse_editor import ParseEditor
from .reader import LinesAutomaton

from pathlib import Path


class Parser(object):
    """Responsible for coordinating all the read modules together.
    And parse one string into a list of readers results.
    """

    def __init__(self, readers=None):
        # Get our own list so it cannot mutate from elsewhere.
        self.readers = readers
        # Instructions collected while parsing.
        self._collect = []

    def collect(self, parsed_object):
        """Intercept ParseEditor object to offer them our edition API
        without passing them to the test runner.
        """
        if isinstance(pe := parsed_object, ParseEditor):
            pe.execute(self)
        else:
            self._collect.append(parsed_object)

    def find_matching_reader(self, lexer) -> "MatchResult" or None:
        """Consume necessary input
        for (exactly) one reader to match at current position.
        """

        # Error out if several readers match: ambiguity.
        matches = []  # [(parsed_result, reader)]
        for reader in self.readers:
            # Spawn a safe version of the lexer for the readers to toy with it..
            lexcopy = lexer.copy()
            try:
                if m := reader.section_match(lexcopy):
                    matches.append((m, reader, lexcopy))
            except NoSectionMatch:
                pass
        if len(matches) > 1:
            readers = [type(r).__name__ for _, r, _ in matches]
            if len(readers) == 2:
                readers = "both readers " + " and ".join(readers)
            else:
                readers = (
                    "all readers " + ", ".join(readers[:-1]) + " and " + readers[-1]
                )
            raise ParseError(f"Ambiguity: {readers} match.", lexer.context)

        # It may be that none matched.
        if len(matches) == 0:
            return None

        # Commit to the lexer winning this match.
        [(match, reader, winlexer)] = matches
        lexer.become(winlexer)

        return match

    def parse(self, lexer):
        """Iteratively hand the lexer to readers so they consume it bit by bit."""

        # One iteration, one collected object.
        self._collect.clear()
        match = None  # Currently being processed.
        while True:

            if not match:
                match = self.find_matching_reader(lexer)

            if not match:

                if lexer.find_empty_line():
                    # It's okay that we have not matched on an empty line
                    # or a pure comment. Consume and move on.
                    if lexer.consumed:
                        break
                    matching_started = False
                    continue
                raise ParseError("No readers matching input.", lexer.context)

            if not isinstance(match, LinesAutomaton):
                # The reader has already produced a valid object.
                self.collect(match)
                if lexer.consumed:
                    break
                match = None
                continue

            # Otherwise, it has returned an automaton
            # that we need to feed with lines until another reader matches.
            automaton = match
            while True:
                if lexer.consumed:
                    self.collect(automaton.terminate())
                    match = None
                    break
                match = self.find_matching_reader(lexer)
                if not match:
                    # Extract only one line to feed the automaton with.
                    # Hand a lexer whose input is only the line.
                    lexcopy = lexer.copy()
                    _, line = lexer.read_until_either(["\n", EOI])
                    lexcopy._lexer.input = line  # Drop anything after the line for it.
                    automaton.feed(lexcopy)
                    continue
                # In case of match, the automaton should be done.
                self.collect(automaton.terminate())
                break
            if not match and lexer.consumed:
                break

        # All input has been parsed.
        return list(self._collect) # Return a copy so it does not mutate here.

    def parse_file(self, filename, path=None, _includer_context=None) -> [object]:
        """Construct a parser to interpret the given file,
        producing a sequence of parsed objects resulting from the various readers.
        """

        # Construct parsing context.
        context = ParseContext(
            filename,
            filepath=path if path else Path(filename).resolve(),
            parser=self,
            includer=_includer_context,
        )

        # Read the file.
        with open(context.filepath, "r") as file:
            input = file.read()

        # Spin a lexer and do the job.
        lexer = ContextLexer(input, context)
        return self.parse(lexer)

    def add_readers(self, readers):
        """Make the parser understand new sections types."""
        self.readers += readers

    def remove_readers(self, to_remove):
        """Make the parser forget about some sections types.
        Readers are removed if to_remove(reader) yields true.
        """
        self.readers = [r for r in self.readers if not to_remove(r)]
