from exceptions import TestSetError

from pathlib import Path


class TestSet(object):
    """The set is responsible for running tests while holding a consistent state:
        - One temporary folder to run the tests within.
        - One input folder to find source data within.
        - One shell command line to be run to evaluate the test.
        - A set of checkers verifying the output of the command:
    The test set is fed with instructions like actors (changing the above state)
    or run statements to actually perform the test and produce reports.
    """

    def __init__(self, input_folder, sandbox_folder):
        """Temporary test folder will be created within the sandox folder,
        the sandbox folder will be created if non-existent.
        """

        self.input_folder = inp = Path(input_folder)
        self.sandbox_folder = sbx = Path(sandbox_folder)

        if not inp.exists():
            raise TestSetError(f"Could not find input folder: {inp}.")

        if not sbx.exists():
            print(f"Creating sandbox folder: {sbx}.")
            sbx.mkdir()

        # Pick a dummy unused name when it's time to run the tests.
        self.test_folder = None

        self.command = None
        self.checkers = set()

    def change(self, actor):
        """Process action to modify environment before the next test."""
        assert False  # HERE
