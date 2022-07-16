"""The EXITCODE statement sets up the expected return code
for the next executed command(s):

    # Example.
    EXITCODE 0

"""

from checker import Checker
from reader import Reader


class ExitCode(Checker):

    expecting_code = True

    def __init__(self, code, position):
        self.code = code
        self.position = position

    def check(self, code, _, __):
        if self.code == code:
            return None
        return f"Expected return code {self.code}, got {code} instead."


class ExitCodeReader(Reader):

    keyword = "EXITCODE"

    def match(self, input, context):
        self.introduce(input)
        if not (code := self.read_split()):
            l.error("Unexpected end of file while reading expected exit code.")
        try:
            code = int(code)
        except ValueError:
            self.error(f"Expected exit code, found {repr(code)}", len(code))
        return self.hard_match(ExitCode(code, context.position))
