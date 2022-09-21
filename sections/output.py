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


Even with the 'exact' mode, differences are tolerated with actual output:
    - Special tokens are expanded in expected output:
        - <TEST_FOLDER> expands to actual path to current test folder.
        - <INPUT_FOLDER> expands to actual path to current input folder.
        ⇒ TODO: allow escaping these token by setting it within this section.
    - terminal escape codes are removed from actual output.
    ⇒ TODO: allow keeping them.
"""

from actor import Actor
from checker import Checker
from exceptions import ParseError, SourceError, delineate_string
from reader import Reader, LinesAutomaton

import re

OUTPUT_CHANNELS = ("stdout", "stderr")


def check_output_channel(channel):
    if channel not in OUTPUT_CHANNELS:
        raise SourceError(
            f"Invalid output channel name: {repr(channel)}. "
            f"Valid names: {', '.join(OUTPUT_CHANNELS)}."
        )


def expand(runner, expected_output) -> str:
    """Resolve <TEST_FOLDER> tokens. Hardcoded for now."""
    test_folder = str(runner.test_file_path(""))
    input_folder = str(runner.input_file_path(""))
    result = expected_output
    result = result.replace("<TEST_FOLDER>", test_folder)
    result = result.replace("<INPUT_FOLDER>", input_folder)
    return result


# Attempt to capture possible terminal escape codes.
escapes = re.compile(r"\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]")


def unescape(output) -> str:
    """Remove escape codes from the string."""
    return escapes.sub("", output)


class OutputChecker(Checker):
    def __init__(self, channel, context):
        check_output_channel(channel)
        self.channel = channel
        self.expecting_stdout = channel == "stdout"
        self.expecting_stderr = channel == "stderr"
        self.context = context


class EmptyOutput(OutputChecker):
    """This degenerated checker expects no output."""

    def check(self, rn, _, stdout, stderr):
        output = eval(self.channel).decode("utf-8")
        if not output:
            return None
        return f"Expected no output on {self.channel}, but got:\n{output}"


class ExactOutput(OutputChecker):
    """Expects to find exactly the given string as output."""

    def __init__(self, output, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.expected_output = output

    def check(self, rn, _, stdout, stderr):
        output = eval(self.channel).decode("utf-8")
        output, eout = unescape(output), output # Keep one escaped version for message.
        expected_output = expand(rn, self.expected_output)
        if output == expected_output:
            return None
        # Find unambiguous markers to display the result.
        expected = delineate_string(expected_output)
        if not output:
            actual = "found nothing instead."
        else:
            actual = delineate_string(eout)
            actual = f"found instead:\n{actual}"
        return f"Expected to find on {self.channel}:\n{expected}\n{actual}\n"


class OutputSubstring(OutputChecker):
    """Expect to find the given message within the output, irrespective of whitespace."""

    def __init__(self, needle, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.needle = needle

    def check(self, rn, _, stdout, stderr):
        hay = eval(self.channel).decode("utf-8")
        hay, ehay = unescape(hay), hay # Keep one escaped version for error message.
        needle = expand(rn, self.needle)
        # Normalize.
        haystack, needle = (" ".join(s.split()) for s in (hay, needle))
        if needle in haystack:
            return None
        if not hay:
            actual = "found nothing instead."
        else:
            actual = f"found instead:\n{ehay}"
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
