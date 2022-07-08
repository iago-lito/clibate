from actor import Actor
from checker import Checker
from exceptions import TestSetError, SourceError

from pathlib import Path
from tempfile import TemporaryFile
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

        self.checkers = []
        # A "test" result is a name + all reports by current checkers.
        self.tests = []  # [(name, {checker: report (None on success)})]

        # Whenever the command is run, record output for the checkers to work on.
        self.stdout = None  # raw bytes
        self.stderr = None  # raw bytes
        self.exitcode = None  # integer

        # Some edits made to files are only temporary,
        # save previous states in temporary files to retrieve them
        # after each test.
        self.backups = {}  # {filepath: tempfile}
        # The tempfile contains the data as it was when the file was created
        # or after the last test was run.
        # If a file does not have an associated backup,
        # then it has not undergone temporary changes that need a reset.

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
        """Delete the whole test folder and clear backup data."""
        shu.rmtree(self.test_folder)
        for temp in self.backups.values():
            temp.close()
        self.backups.clear()

    def change(self, object):
        """Process action to modify environment before the next test."""
        if isinstance(actor := object, Actor):
            actor.execute(self)
        elif isinstance(checker := object, Checker):
            self.add_checkers([checker])
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

    def add_checkers(self, checkers, exclude=True):
        """Append new checkers to the checkers set.
        if 'exclude' is set, first remove all checkers
        with overlapping expectations.
        """
        if exclude:
            expectations = set()
            for c in checkers:
                for e in Checker._expectations:
                    if eval(f"c.expecting_{e}"):
                        expectations.add(e)
            self.clear_checkers(expectations)
        self.checkers += checkers

    def run_checks(self, name) -> bool:
        """Run all checks and gather reports under the given name.
        Return False if some checks failed.
        """
        success = True
        reports = {}
        for checker in self.checkers:
            r = checker.check(self.exitcode, self.stdout, self.stderr)
            if r is not None:
                success = False
            reports[checker] = r
        self.tests.append((name, reports))
        return success

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

        # Gather only failed reports.
        failed = []
        for name, reports in self.tests:
            failed_reports = {}
            for checker, rep in reports.items():
                if rep is not None:
                    failed_reports[checker] = rep
            if failed_reports:
                failed.append((name, failed_reports))

        n_total, n_failed = len(self.tests), len(failed)
        n_ok = n_total - n_failed
        if failed:
            print(
                f"\n{red}🗙{reset} {n_failed} test{plur(n_failed)} "
                f"ha{plur(n_failed, 've', 's')} failed:\n"
            )
            for name, reports in failed:
                print(f"{blue}{name}{reset}")
                for report in reports.values():
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

    def clear_checkers(self, expectations=Checker._expectations):
        """Clear all checkers setting such expectations."""
        new_checkers = []
        for c in self.checkers:
            include = True
            for e in expectations:
                if eval(f"c.expecting_{e}"):
                    include = False
                    break
            if include:
                new_checkers.append(c)
        self.checkers = new_checkers

    def canonicalize_test_path(self, path):
        """When given a simple local string or a full path, normalize."""
        if path == Path(path).resolve():
            return path
        return Path(self.test_folder, path).resolve()

    def backup_file(self, filename, override):
        """Create a temporary backup for this file name.
        Override existing backup if requested.
        """
        if not (path := self.canonicalize_test_path(filename)).exists():
            raise TestSetError(f"Cannot backup unexistent file {path}.")
        if path in self.backups and not override:
            return
        # Create a new backup.
        temp = TemporaryFile()
        with open(path, "rb") as file:
            temp.write(file.read())
        # Close existing files to not wait for gc.
        try:
            self.backups.pop(path).close()
        except KeyError:
            pass
        # Reset cursor for future reads.
        temp.seek(0)
        self.backups[path] = temp

    def delete_backup(self, filename):
        """Forget about previous revision of the file."""
        path = self.canonicalize_test_path(filename)
        self.backups.pop(path).close()

    def restore_file(self, filename, keep_backup, error_if_no_backup=True):
        """Transform the file so it becomes like the last available backup of it."""
        path = self.canonicalize_test_path(filename)
        try:
            temp = self.backups[path]
        except KeyError:
            if error_if_no_backup:
                raise TestSetError(f"No available backup to restore file {path}.")
            else:
                # Consider the file is restored.
                return
        with open(path, "wb") as file:
            file.write(temp.read())
        if not keep_backup:
            self.delete_backup(path)
        else:
            # Reset cursor for future reads
            temp.seek(0)

    def restore_all_files(self, *args, **kwargs):
        """All files with a backup will be restored."""
        paths = [*self.backups.keys()]
        for path in paths:
            self.restore_file(path, *args, **kwargs)
