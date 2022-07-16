"""The basic stdout/stderr sections set up simple expectations on either output channel.

    stdout: # (or 'stderr:')
        Output lines to be matched
        irrespective of whitespace.
        It's okay if other things also appear in the output.

    stdout:: EOO # (or 'stderr::')
        (dedented) Exact output to be matched.
    EOO

    stdout: * # Clear expectations regarding output.
    # (or 'stderr:')

    stdout::* # Expect exactly no output.
    # (or 'stderr::')

"""

from actor import Actor
from checker import Checker
from exceptions import ParseError, SourceError, delineate_string
from lexer import Lexer
from reader import Reader, LinesAutomaton


OUTPUT_CHANNELS = ("stdout", "stderr")


def check_output_channel(channel):
    if channel not in OUTPUT_CHANNELS:
        raise SourceError(
            f"Invalid output channel name: {repr(channel)}. "
            f"Valid names: {', '.join(OUTPUT_CHANNELS)}."
        )


class OutputChecker(Checker):
    def _set_output_channel(self, channel):
        check_output_channel(channel)
        self.channel = channel
        self.expecting_stdout = channel == "stdout"
        self.expecting_stderr = channel == "stderr"


class EmptyOutput(OutputChecker):
    """This degenerated checker expects no output."""

    def __init__(self, channel, position):
        self._set_output_channel(channel)
        self.position = position

    def check(self, _, stdout, stderr):
        output = eval(self.channel).decode("utf-8")
        if not output:
            return None
        return f"Expected no output on {self.channel}, but got:\n{output}"


class ExactOutput(OutputChecker):
    """Expects to find exactly the given string as output."""

    def __init__(self, channel, expected_output, position):
        self._set_output_channel(channel)
        self.expected_output = expected_output
        self.position = position

    def check(self, _, stdout, stderr):
        output = eval(self.channel).decode("utf-8")
        if output == self.expected_output:
            return None
        # Find unambiguous markers to display the result.
        expected = delineate_string(self.expected_output)
        if not output:
            actual = "found nothing instead."
        else:
            actual = delineate_string(output)
            actual = f"found instead:\n{actual}"
        return f"Expected to find on {self.channel}:\n{expected}\n{actual}\n"


class OutputSubstring(OutputChecker):
    """Expect to find the given message within the output, irrespective of whitespace."""

    def __init__(self, channel, needle, position):
        self._set_output_channel(channel)
        self.needle = needle
        self.position = position

    def check(self, _, stdout, stderr):
        hay = eval(self.channel).decode("utf-8")
        # Normalize.
        haystack, needle = (" ".join(s.split()) for s in (hay, self.needle))
        if needle in haystack:
            return None
        if not hay:
            actual = "found nothing instead."
        else:
            actual = f"found instead:\n{hay}"
        return f"Expected to find on {self.channel}:\n{needle}\n{actual}"


class OutputClearer(Actor):
    """Remove any expectation regarding output."""

    def __init__(self, channel):
        check_output_channel(channel)
        self.channel = channel

    def execute(self, ts):
        ts.clear_checkers([self.channel])


class OutputReader(Reader):
    """Parse either section type."""

    def __init__(self, channel):
        check_output_channel(channel)
        self.keyword = channel
        self.channel = channel

    def match(self, input, context):
        channel = self.channel
        self.introduce(input)
        colon = self.check_colon_type()
        pos = context.position

        if colon == "::":
            if self.find("*"):
                return self.hard_match(EmptyOutput(channel, pos))

            output = self.read_heredoc_like(name=channel)
            return self.hard_match(ExactOutput(channel, output, pos))

        if colon == ":":
            if self.find("*"):
                return self.hard_match(OutputClearer(channel))
            return self.soft_match(OutputSubstringAutomaton(channel, pos))


class OutputSubstringAutomaton(LinesAutomaton):
    def __init__(self, channel, position):
        check_output_channel(channel)
        self.position = position
        self.channel = channel
        self.output = []

    def feed(self, line, _):
        self.output.append(Lexer(line).read_string_or_raw_line()[0])

    def terminate(self):
        total = " ".join(self.output)
        if not total.strip():
            raise ParseError(f"Blank expected {self.channel} in last section.")
        return OutputSubstring(self.channel, total, self.position)
