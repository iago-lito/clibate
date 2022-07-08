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
        self.reports = []  # [(name, report (None on success))]

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

    def run_checks(self, name):
        """Run all checks and gather reports under the given name."""
        for checker in self.checkers.values():
            report = checker.check(self.exitcode, self.stdout, self.stderr)
            self.reports.append((name, report))

    def report(self):
        """Organize all reports into a nice summary."""

        # Escape codes for coloring output.
        red = "\x1b[31m"
        blue = "\x1b[34m"
        green = "\x1b[32m"
        yellow = "\x1b[33m"
        reset = "\x1b[0m"

        def plur(n, p="s", s=""):
            return p if n > 1 else s

        failed = [(name, report) for name, report in self.reports if report is not None]
        n_total, n_failed = len(self.reports), len(failed)
        n_ok = n_total - n_failed
        if failed:
            print(
                f"\n{red}🗙{reset} {n_failed} test{plur(n_failed)} "
                f"ha{plur(n_failed, 've', 's')} failed:\n"
            )
            for name, report in failed:
                print(f"{blue}{name}{reset}")
                print(report, end="\n\n")
            print(
                f"{blue}{n_total}{reset} test{plur(n_total)} run: "
                f"{green}{n_ok}{reset} success{plur(n_ok, 'es')}, "
                f"{red}{n_failed}{reset} failure{plur(n_failed)}."
            )
            return
        if n_ok:
            symbol = f"{green}✔{reset}"
            colon = ":"
        else:
            symbol = f"{yellow}??"
            colon = "?"
        print(f"\n{symbol}{reset} Success{colon} {n_total} test{plur(n_total)} run.")
