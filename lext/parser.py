from .context import ParseContext, ContextLexer, EOI
from .exceptions import ParseError, NoSectionMatch
from .parse_editor import ParseEditor
from .reader import SplitAutomaton

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

    def find_matching_reader(self, lexer) -> [object]:
        """Consume necessary input
        for one or zero reader to match at current position.
        """

        # Error out if several readers match: ambiguity.
        matches = []  # [(parsed_result, reader)]
        for reader in self.readers:
            # Spawn a safe version of the lexer for the readers to toy with it..
            lexcopy = lexer.copy()
            try:
                m = reader.section_match(lexcopy)
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
            return []

        # Commit to the lexer winning this match.
        [(match, reader, winlexer)] = matches
        lexer.become(winlexer)

        return [match]

    def parse(self, lexer):
        """Iteratively hand the lexer to readers so they consume it bit by bit."""

        # One iteration, one collected object.
        self._collect.clear()
        match = []  # Currently being processed: [], [None] or [object]
        while True:

            if match == []:
                match = self.find_matching_reader(lexer)

            if match == []:
                raise ParseError("No readers matching input.", lexer.context)

            if match == [None]:
                # This is a sign sent from an ignorer:
                # parsing is correct but there is nothing interesting here to parse.
                if lexer.consumed:
                    break
                match = []
                continue

            if not isinstance(match[0], SplitAutomaton):
                # The reader has already produced a valid object.
                self.collect(match[0])
                if lexer.consumed:
                    break
                match = []
                continue

            # Otherwise, it has returned an automaton
            # that we need to feed with input bits until another reader matches.
            automaton = match[0]
            while True:
                if lexer.consumed:
                    if (m := automaton.terminate()) is not None:  # Otherwise ignored.
                        self.collect(m)
                    match = []
                    break
                match = self.find_matching_reader(lexer)
                if match == []:
                    # Extract only one bit to feed the automaton with.
                    # Hand a lexer whose input is only the given bit.
                    lexcopy = lexer.copy()
                    bit = automaton.split(lexer)
                    lexcopy._lexer.input = bit  # Drop anything after the bit for it.
                    automaton.feed(lexcopy)
                    continue
                if match == [None]:
                    # Ignore what has just been consumed.
                    continue
                # In case of match, the automaton should be done.
                if (m := automaton.terminate()) is not None:
                    self.collect(m)
                break
            if match == [] and lexer.consumed:
                break

        # All input has been parsed.
        return list(self._collect)  # Return a copy so it does not mutate here.

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
