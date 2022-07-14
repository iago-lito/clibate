"""The Success section is the first sophisticated section
to be used directly by end user.
It sets up:
    - an expected 0 return code
    - an expected stdout
    - an expected empty stderr
    - a name for the test (optional)
Then it:
    - runs the test command
    - checks the result
    - restore all saved files from backups, consuming backups.
    - produces a log message before the actual TestSet.report is invoked

Also, the expected stdout is not checked exactly.
It is only checked that the expected string can be found within stdout,
irrespective of whitespace.

    Success: <Oneline name for the test.>
        this string must appear within stdout

With no stdout lines provided, stdout is ignored
and the command is just expected to succeed.
"""

from .exit_code import ExitCode
from actor import Actor
from exceptions import ParseError
from lexer import Lexer
from reader import Reader, LinesAutomaton
from utils import StdoutSubChecker, EmptyStderr


class Success(Actor):
    def __init__(self, name, position, stdout):
        self.name = name
        self.position = position
        self.stdout = stdout

    def execute(self, ts):
        # Set up common checkers.
        ts.add_checkers([ExitCode(0), StdoutSubChecker(self.stdout), EmptyStderr()])
        # Display message before running the test.
        if self.name:
            ts.test_name = self.name
        message = ts.test_name.rstrip(".")
        print(message + "..", end="", flush=True)
        ts.run_command(self.position)
        # Close message with test results.
        # Reports can still be displayed by the TestSet later.
        red = "\x1b[31m"
        green = "\x1b[32m"
        reset = "\x1b[0m"
        if ts.run_checks(self.position):
            print(f" {green}PASS{reset}")
        else:
            print(f" {red}FAIL{reset}")
        ts.restore_all_files(keep_backup=False)


class SuccessReader(Reader):

    keyword = "Success"

    def match(self, input, context):
        self.introduce(input)
        self.check_colon()
        name = l if (l := self.read_line()) else None
        return self.soft_match(SuccessAutomaton(name, context.position))


class SuccessAutomaton(LinesAutomaton):
    def __init__(self, name, position):
        self.name = name
        self.position = position
        self.stdout = []

    def feed(self, line, _):
        if not Lexer(line).find_empty_line():
            self.stdout.append(line.strip())

    def terminate(self):
        total = " ".join(self.stdout)
        if not total.strip():
            raise ParseError("Blank expected stdout in last Success section.")
        return Success(self.name, self.position, total)
