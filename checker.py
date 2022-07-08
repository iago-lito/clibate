class Checker(object):
    """Checkers are stored within the TestSet and set up expectations about the test
    command outputs.
    """

    def check(self, code, stdout, stderr) -> None or str:
        """Verify that output code is conforming, otherwise produce an error report."""
        return None
