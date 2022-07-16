"""These degenerated checkers expect no output.
"""

from checker import Checker


class EmptyStdout(Checker):

    expecting_stdout = True

    def __init__(self, position):
        self.position = position

    def check(self, _, stdout, __):
        stdout = stdout.decode("utf-8")
        if not stdout:
            return None
        return f"Expected no output on stdout, but got:\n{stdout}"


class EmptyStderr(Checker):

    expecting_stderr = True

    def __init__(self, position):
        self.position = position

    def check(self, _, __, stderr):
        stderr = stderr.decode("utf-8")
        if not stderr:
            return None
        return f"Expected no output on stderr, but got:\n{stderr}"
