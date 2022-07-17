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
    def __init__(self, channel, context):
        check_output_channel(channel)
        self.channel = channel
        self.expecting_stdout = channel == "stdout"
        self.expecting_stderr = channel == "stderr"
        self.context = context


class EmptyOutput(OutputChecker):
    """This degenerated checker expects no output."""

    def check(self, _, stdout, stderr):
        output = eval(self.channel).decode("utf-8")
        if not output:
            return None
        return f"Expected no output on {self.channel}, but got:\n{output}"


class ExactOutput(OutputChecker):
    """Expects to find exactly the given string as output."""

    def __init__(self, output, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.expected_output = output

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

    def __init__(self, needle, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.needle = needle

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

    def execute(self, rn):
        rn.clear_checkers([self.channel])


class OutputReader(Reader):
    """Parse either section type."""

    def __init__(self, channel):
        check_output_channel(channel)
        self.keyword = channel
        self.channel = channel

    def section_match(self, lex):
        self.introduce(lex)
        channel = self.channel
        colon = self.check_colon_type()

        cx = self.keyword_context
        if colon == "::":
            if self.find("*"):
                return EmptyOutput(channel, cx)

            output = self.read_heredoc_like(name=channel)
            return ExactOutput(output, channel, cx)

        if colon == ":":
            if self.find("*"):
                return OutputClearer(channel, cx)
            return OutputSubstringAutomaton(channel, cx)


class OutputSubstringAutomaton(LinesAutomaton):
    def __init__(self, channel, context):
        check_output_channel(channel)
        self.context = context
        self.channel = channel
        self.output = []

    def feed(self, lex):
        self.output.append(lex.read_string_or_raw_line()[0])

    def terminate(self):
        total = " ".join(self.output)
        if not total.strip():
            raise ParseError(
                f"Blank expected {self.channel} in last section.",
                self.context,
            )
        return OutputSubstring(total, self.channel, self.context)
