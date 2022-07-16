"""The EXITCODE statement sets up the expected return code
for the next executed command(s):

    # Example.
    EXITCODE 0   # Expect success.

    EXITCODE 2   # Expect a value of 2.

    EXITCODE +   # Expect non-null value.

    EXITCODE *   # Expect nothing.

"""

from actor import Actor
from checker import Checker
from exceptions import ParseError
from reader import Reader


class ClearExpectedExitCode(Actor):
    def execute(_, ts):
        ts.clear_checkers(["exitcode"])


class ExitCodeChecker(Checker):

    expecting_code = True

    def __init__(self, code, position):
        self.code = code
        self.position = position

    def check(self, code, _, __):

        if self.code == "+":
            if code == 0:
                return f"Expected positive return code, got 0 instead."
            return None

        if self.code == code:
            return None

        return f"Expected return code {self.code}, got {code} instead."


def ExitCode(code, position, lexer=None, backtrack=0):
    """Construct correct Checker or Actor depending on the code."""
    try:
        code = int(code)
    except ValueError:
        if code not in ("*", "+"):
            message = f"Expected exit code, '+' or '*', found {repr(code)}"
            if lexer:
                lexer.error(message, backtrack)
            else:
                raise ParseError(message)
    if code == "*":
        return ClearExpectedExitCode()
    else:
        return ExitCodeChecker(code, position)


class ExitCodeReader(Reader):

    keyword = "EXITCODE"

    def match(self, input, context):
        self.introduce(input)
        if not (code := self.read_split()):
            l.error("Unexpected end of file while reading expected exit code.")
        return self.hard_match(ExitCode(code, context.position, self.lexer, len(code)))
