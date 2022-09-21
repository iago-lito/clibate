"""The Expect section (Expect/Failure) is the first sophisticated section
to be used directly by end user.

Success sets up (by default):
    - an expected 0 return code
    - an expected stdout (specified by user)
    - an expected *empty* stderr
    - an optional name for the test
Failure sets up (by default):
    - an expected nonzero return code (+).
    - an expected stderr (specified by user)
    - clear expectations regarding stdout
    - an optional name for the test.

Then, they invoke an implicit RUNTEST.

For example:

    success <(exitcode)>: <Oneline name for the test.>
        these lines must appear within stdout
        irrespective of whitespace

    failure <(exitcode)>: <Oneline name for the test.>
        these lines must appear within stderr
        irrespective of whitespace

    success: one-liner for *expected output*, no name provided for the test

    failure (1): one-liner for *expected error output*, no name provided for the test

    success: <Oneline name for the test.>
             *    # Ignore output. (pick last token if name is unquoted)

    failure (+): *   # Expect failure no matter the errors written.

    success (2): *   # Expect "success" no matter stdout, but with exact code 2.

To expect exact verbatim output messages, use double-colon sections and heredoc markers.

    success:: <Oneline name for the test.> EOO   # (pick last token if name is unquoted)
        these lines must appear verbatim (dedented) on stdout
        matching whitespace exactly
    EOO

    failure:: <Oneline name for the test.> EOE   # (pick last token if name is unquoted)
        these lines must appear verbatim (dedented) on stderr
        matching whitespace exactly
    EOE

With double-colon and the star, expect exact empty output.

    success:: *  # Expect empty stdout and zero exit code.

    failure:: This test expects no stderr output but nonzero exit code.
              *


"""

from .exit_code import ExitCode
from .output import EmptyOutput, ExactOutput, OutputSubstring, OutputSubstringAutomaton
from actor import Actor
from exceptions import ParseError
from reader import Reader, LinesAutomaton


class Expect(Actor):
    def __init__(self, name, success, context, output_checker, exit_code):
        self.name = name
        self.success = success
        self.context = context
        self.output_checker = output_checker
        self.exit_code = exit_code

    def execute(self, rn):
        # Setup checkers.
        checkers = []

        if self.output_checker:
            checkers.append(self.output_checker)
        else:
            # Remove if no particular expectation is set.
            rn.clear_checkers(["stdout" if self.success else "stderr"])

        # '*' code yields an actor to erase checkers, not an actual checker.
        if isinstance(self.exit_code, Actor):
            self.exit_code.execute(rn)
        else:
            checkers.append(self.exit_code)

        if self.success:
            # Expect nothing on stderr.
            checkers.append(EmptyOutput("stderr", self.context))
        else:
            # Ignore stdout.
            rn.clear_checkers(["stdout"])

        rn.add_checkers(checkers)
        rn.run_test(self.context, self.name)


class ExpectReader(Reader):

    keywords = ("success", "failure")

    def __init__(self, success: bool):
        self.success = success
        self.failure = not success  # Just to ease reading
        self.keyword = self.keywords[self.failure]

    def section_match(self, lex):
        self.introduce(lex)

        # Retrieve exitcode.
        # Both sections accept it, but they don't default to the same.
        context = self.lstrip().context
        try:
            code = self.read_tuple(1)
        except ParseError:
            if self.success:
                code = 0
            else:
                code = "+"
        exit_code = ExitCode(code, context)

        # Understand global line type.
        c = self.check_colon_type()

        context = self.lstrip(newline=False).context
        name, star, raw = self.read_name_and_star()

        channel = ["stdout", "stderr"][self.failure]
        if c == "::" and star:
            # Exactly no output is expected.
            self.check_empty_line()
            checker = EmptyOutput(channel, context)

        elif c == "::" and not star:
            # Expect exact output.
            if raw and not name:
                self.error(f"No marker found to delimitate exact expected {channel}.")
            if raw:
                # Last token in the name was actually the marker.
                try:
                    name, eoo = name.rsplit(None, 1)
                except ValueError:
                    eoo = name
                    name = ""
                output = self.read_heredoc_like(name=channel, EOR=eoo)
            else:
                output = self.read_heredoc_like(name=channel)
            checker = ExactOutput(output, channel, context)

        elif c == ":" and star:
            # Expect nothing particular from the output.
            self.check_empty_line()
            checker = None

        elif c == ":" and not star:
            # Soft match.
            return ExpectAutomaton(name, self.success, self.keyword_context, exit_code)

        # Hard match otherwise.
        return Expect(name, self.success, self.keyword_context, checker, exit_code)

    def read_name_and_star(self) -> (str, bool, bool):
        """The section name may be followed by a star,
        and we need backtracking to find it in case it's a raw read.
        If we don't, go seek whether it's standing on next line.
        """
        name, raw = self.read_string_or_raw_line()
        if raw:
            # Seek with a backtrack within the name.
            star = False
            if name:
                try:
                    n, s = name.rsplit(None, 1)
                    if s == "*":
                        name = n
                        star = True
                except ValueError:
                    if name == "*":
                        star = True
                        name = ""
            if not star:
                # Seek possible star in next line(s).
                star = self.find("*")
            return name, star, True
        # Easier in case of a quoted read.
        return name, self.find("*"), False


class ExpectAutomaton(LinesAutomaton):
    """Wraps the OutputSubstringAutomaton and forwards feed to it."""

    def __init__(self, name, success, context, exit_code):
        self.name = name
        self.context = context
        self.success = success
        self.channel = ["stderr", "stdout"][success]
        self.exit_code = exit_code
        self.n_lines = 0
        self.aut = OutputSubstringAutomaton(self.channel, context)

    def feed(self, lex):
        if lex.find_empty_line():
            return
        self.n_lines += 1
        self.aut.feed(lex)

    def terminate(self):
        if self.n_lines:
            name = self.name
            checker = self.aut.terminate()
        else:
            # Backtrack: the line looking like a raw 'name'
            # was actually expected output, and there is no name.
            name = ""
            needle = self.name
            checker = OutputSubstring(needle, self.channel, self.context)
        return Expect(name, self.success, self.context, checker, self.exit_code)
