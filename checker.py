class Checker(object):
    """Checkers are stored within the TestRunner and set up expectations about the test
    command outputs.
    Checkers are characterized by a triplet of boolean, asserting whether:
        - they expect something from exitcode
        - they expect something from stdout
        - they expect something from stderr
    This is helpful to avoid inserting inconsistent expectations into the TestRunner.

    To subclass:
        - implement `self.check()`
        -    set up `self.expecting_*` flag(s)
        - make sure `self.context` is available to produce useful failure reports.
    """

    _expectations = ("code", "stdout", "stderr")

    expecting_code = False
    expecting_stdout = False
    expecting_stderr = False

    def __init__(self, context):
        """Trivial default."""
        self.context = context

    def check(self, code, stdout, stderr) -> None or str:
        """Verify that output code is conforming, otherwise produce an error report."""
        return None
