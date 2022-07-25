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
    def execute(_, rn):
        rn.clear_checkers(["exitcode"])


class ExitCodeChecker(Checker):

    expecting_code = True

    def __init__(self, code, context):
        self.code = code
        self.context = context

    def check(self, _rn, code, _, __):

        if self.code == "+":
            if code == 0:
                return f"Expected positive return code, got 0 instead."
            return None

        if self.code == code:
            return None

        return f"Expected return code {self.code}, got {code} instead."


def ExitCode(code, context):
    """Construct correct Checker or Actor depending on the code."""
    try:
        code = int(code)
    except ValueError:
        if code not in ("*", "+"):
            raise ParseError(
                f"Expected exit code, '+' or '*', found {repr(code)}",
                cx=context,
            )
    if code == "*":
        return ClearExpectedExitCode()
    else:
        return ExitCodeChecker(code, context)


class ExitCodeReader(Reader):

    keyword = "EXITCODE"

    def section_match(self, lex):
        self.introduce(lex)
        cx = lex.lstrip().context
        if not (code := self.read_split()):
            lex.error("Unexpected end of file while reading expected exit code.")
        return ExitCode(code, cx)
