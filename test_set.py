from actor import Actor
from checker import Checker
from exceptions import TestSetError, SourceError

from pathlib import Path
import os
import shutil as shu
import subprocess as sp


class TestSet(object):
    """The set is responsible for running tests while holding a consistent state:
        - One temporary folder to run the tests within.
        - One input folder to find source data within.
        - One shell command line to be run to evaluate the test.
        - A set of checkers verifying the output of the command:
    The test set is fed with instructions like actors (changing the above state)
    or run statements to actually perform the test and produce reports.

    The test set API is presented to the actors so they can safely modify it.
    """

    def __init__(self, input_folder, sandbox_folder, prepare=None):
        """Temporary test folder will be created within the sandox folder,
        the sandbox folder will be created if non-existent.
        'prepare' is a sequence of commands to be run before after creating the test
        folder.
        """

        self.input_folder = inp = Path(input_folder).resolve()
        self.sandbox_folder = sbx = Path(sandbox_folder).resolve()
        self._prepare = prepare if prepare else []

        if not inp.exists():
            raise TestSetError(f"Could not find input folder: {inp}.")

        if not sbx.exists():
            print(f"Creating sandbox folder: {sbx}.")
            sbx.mkdir()

        # Pick a dummy unused name when it's time to run the tests.
        self.test_folder = None

        self.command = None

        # No duplicate checkers are allowed unless they have different types.
        self.checkers = {}  # {type(checker): checker}

        # Whenever the command is run, record output for the checkers to work on.
        self.stdout = None  # raw bytes
        self.stderr = None  # raw bytes
        self.exitcode = None  # integer

    def prepare(self):
        """Pick a name for the test folder and send prepare commands."""
        i = 0
        while (p := Path(self.sandbox_folder, f"test_{i}")).exists():
            i += 1
        p.mkdir()
        self.test_folder = p.absolute()
        for cmd in self._prepare:
            print("$ " + cmd)
            if os.system(cmd):
                raise TestSetError(f"Test preparation command failed.")
        # Also, move to test folder:
        os.chdir(self.test_folder)

    def cleanup(self):
        """Delete the whole test folder."""
        shu.rmtree(self.test_folder)

    def change(self, object):
        """Process action to modify environment before the next test."""
        if isinstance(actor := object, Actor):
            actor.execute(self)
        elif isinstance(checker := object, Checker):
            self.add_checker(checker)
        else:
            raise SourceError(f"Invalid change object type: {type(object).__name__}.")

    def is_input_file(self, filename) -> bool:
        """Test whether the given file exists in the input folder."""
        return Path(self.input_folder, filename).exists()

    def check_input_file(self, filename):
        """Raise if given file does not exist."""
        if not self.is_input_file(filename):
            raise TestSetError(
                f"Could not find file {repr(filename)} "
                f"in input folder {self.input_folder}."
            )

    def copy_from_input(self, filename, destination_name):
        """Bring file from input to test folder, erasing existing ones."""
        shu.copy2(
            Path(self.input_folder, filename), Path(self.test_folder, destination_name)
        )

    def create_file(self, name, content):
        """Create file within the test folder (erasing existing ones)."""
        with open(Path(self.test_folder, name), "w") as file:
            file.write(content)

    def update_command(self, command):
        """Replace/update the shell command to run for the tests."""
        self.command = command

    def run_command(self):
        """Run the command and record all output."""
        if not self.command:
            raise TestSetError(f"No command to be run.")
        process = sp.Popen(self.command, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
        process.wait()
        self.exitcode = process.returncode
        self.stdout = process.stdout.read()
        self.stderr = process.stderr.read()

    def add_checker(self, c):
        """Append a new checker to the checkers set."""
        self.checkers[type(c)] = c
