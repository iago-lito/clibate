from actor import Actor
from checker import Checker
from exceptions import TestRunError, SourceError, colors as c

from inspect import getfullargspec
from pathlib import Path
from tempfile import TemporaryFile
import os
import shutil as shu
import subprocess as sp
import sys
import textwrap as tw


class TestRunner(object):
    """Responsible for running tests while holding a consistent state:
        - One temporary folder to run the tests within.
        - One input folder to find source data within.
        - One shell command line to be run to evaluate the test.
        - A set of checkers verifying the output of the command:
    The test runner is fed with instructions like actors (changing the above state)
    or run statements to actually perform the test and produce reports.

    The test runner API is presented to the actors so they can safely modify it.
    """

    __test__ = False  # Avoid being collected by Pytest.

    def __init__(
        self,
        input_folder,
        sandbox_folder,
        parser,
        id=None,
        prepare=None,
        context=None,
    ):
        """Temporary test folder will be created within the sandox folder,
        the sandbox folder will be created if non-existent.
        'prepare' is a sequence of commands to be run before after creating the test
        folder.
        """

        # Uniquely identify the set to avoid test folders collisions within the sandbox.
        self.id = id if id is not None else "set"

        # A parser is needed to parser included files.
        self.parser = parser

        # A context is provided if the runner is spawn from eg. an `include*:` section.
        self.context = context

        self.input_folder = inp = Path(input_folder).resolve()
        self.sandbox_folder = sbx = Path(sandbox_folder).resolve()
        self.prepare_commands = prepare if prepare else []

        if not inp.exists():
            raise TestRunError(
                f"Could not find input folder: {repr(str(inp))}.",
                self.context,
            )

        if not sbx.exists():
            print(f"Creating sandbox folder: {repr(str(sbx))}.")
            sbx.mkdir()

        # Pick a dummy unused name when it's time to run the tests.
        self.test_folder = None

        # The command to be run and where it has been defined.
        self.command = None
        self.command_context = None

        self.checkers = []
        # A "test" result is a name + run context + all reports by current checkers.
        # Checkers also hold their own context: they may be defined prior to test run.
        self.tests = []  # [(name, context, {checker: report (None on success)})]
        # The test name is set in advance by actors.
        self.test_name = None
        self.test_name_context = None

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

    @property
    def current_test_name(self):
        return self.test_name if self.test_name else "<UNNAMED TEST>"

    def prepare(self):
        """Pick a name for the test folder and send prepare commands."""
        i = 0
        path = lambda i: Path(
            self.sandbox_folder, "test_" + self.id + (f"-{i}" if i else "")
        )
        while (p := path(i)).exists():
            i += 1
        p.mkdir()
        self.test_folder = p.absolute()
        for cmd in self.prepare_commands:
            print("$ " + cmd)
            if os.system(cmd):
                raise TestRunError(f"Test preparation command failed.", self.context)
        # Also, move to test folder:
        os.chdir(self.test_folder)

    def cleanup(self):
        """Delete the whole test folder and clear backup data."""
        shu.rmtree(self.test_folder)
        for temp in self.backups.values():
            temp.close()
        self.backups.clear()

    def execute(self, instruction):
        """Process action to modify environment before the next test.
        Catch TestRunError emitted by the instruction,
        and fill their default context from `instruction.context` so they have one
        before forwarding up.
        """
        try:
            if isinstance(actor := instruction, Actor):
                actor.execute(self)
            elif isinstance(checker := instruction, Checker):
                self.add_checkers([checker])
            else:
                raise SourceError(
                    f"Invalid change object type: {type(instruction).__name__}."
                )
        except TestRunError as e:
            if not e.context:
                try:
                    e.context = instruction.context
                except AttributeError as a:
                    raise SourceError(
                        f"Missing context information "
                        f"on instruction {type(instruction).__name__}."
                    ) from a
            raise

    def setup_and_run(self, instructions, report=True) -> None or bool:
        """Prepare, run given instructions, report then cleanup.
        If report is asked, return False if some checks failed
        and the reports are not all empty.
        """
        exception = True
        try:
            self.prepare()
            for inst in instructions:
                self.execute(inst)
            if report:
                exception = False
                return self.report()
        except:
            print(
                f"Exception caught during test run {repr(self.id)}: " "cleaning up..",
                end="",
            )
            raise
        else:
            exception = False
        finally:
            self.cleanup()
            if exception:
                print(" done.")

    for folder in ("sandbox", "input", "test"):
        exec(
            tw.dedent(
                f'''
    def {folder}_file_path(self, filename) -> Path:
        """Construct valid, absolute, canonicalized path
        to a file in {folder} folder.
        """
        return Path(self.{folder}_folder, filename)

    def is_{folder}_file(self, filename) -> bool:
        """Test whether the given file exists in the {folder} folder."""
        return self.{folder}_file_path(filename).exists()

    def check_{folder}_file(self, filename) -> Path:
        """Raise if given file does not exist,
        otherwise, return canonical path to it.
        """
        if not self.is_{folder}_file(filename):
            raise TestRunError(
                f"Could not find file {{repr(filename)}} "
                f"in {folder} folder {{self.{folder}_folder}}."
            )
        return self.{folder}_file_path(filename)
    '''
            )
        )
    del folder

    def copy_from_input(self, source, target):
        """Bring file from input to test folder, erasing existing ones."""
        rsource = Path(self.input_folder, source).resolve()
        rtarget = Path(self.test_folder, target).resolve()
        try:
            shu.copy2(rsource, rtarget)
        except Exception as e:
            raise TestRunError(
                f"Could not copy file {source} to {target}. "
                f"  ({rsource}\nto {rtarget})"
            )

    def create_file(self, name, content):
        """Create file within the test folder (erasing existing ones)."""
        path = Path(self.test_folder, name).resolve()
        try:
            with open(path, "w") as file:
                file.write(content)
        except Exception as e:
            raise TestRunError(
                f"Could not create file ({name}){c.grey}({path}){c.reset}."
            )

    def update_test_name(self, name, context):
        """Replace/update the test name to identify the tests."""
        self.test_name = name
        self.test_name_context = context

    def update_command(self, command, context):
        """Replace/update the shell command to run for the tests."""
        self.command = command
        self.command_context = context

    def run_command(self):
        """Run the command and record all output."""
        if not self.command:
            raise TestRunError(f"No command to be run.")
        try:
            process = sp.Popen(self.command, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
            process.wait()
        except Exception as e:
            cmdref = (
                f"in {self.command_context.ref}"
                if self.command_context
                else "<nowhere>"
            )
            raise TestRunError(
                "Could not run the testing command. "
                f"The command is:\n{self.command}\n"
                f"and was defined {cmdref}."
            )
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

    def run_checks(self, run_context) -> bool:
        """Run all checks and gather reports under the current test name
        and their current context.
        Return False if some checks failed.
        The test name is reset.
        """
        success = True
        reports = {}
        # Only use the run_context if no test name was set.
        if self.test_name:
            context = self.test_name_context
        else:
            context = run_context
        for checker in self.checkers:
            r = checker.check(self.exitcode, self.stdout, self.stderr)
            if r is not None:
                success = False
            reports[checker] = r
        self.tests.append((self.current_test_name, context, reports))
        self.test_name = None
        return success

    def run_test(self, context, name=None):
        """All-in-one aggregated method to run one test."""
        # Setup name if needed.
        if name:
            self.update_test_name(name, context)
        name = self.current_test_name

        # Log message.
        message = name.rstrip(".")
        print(f"  {message}..", end="", flush=True)

        # Run.
        self.run_command()

        # Check and log result.
        if self.run_checks(context):
            print(f" {c.green}PASS{c.reset}")
        else:
            # Failed test reports are still saved for later by self.run_checks().
            print(f" {c.red}FAIL{c.reset}")

        self.restore_all_files(keep_backup=False)

    def report(self) -> bool:
        """Organize all reports into a nice summary.
        Return False if the summary contains failed tests reports.
        """

        def plur(n, p="s", s=""):
            return p if n > 1 else s

        eprint = lambda *args, **kwargs: print(*args, file=sys.stderr, **kwargs)

        # Gather only failed reports.
        failed = []
        for name, context, reports in self.tests:
            failed_reports = {}
            for checker, rep in reports.items():
                if rep is not None:
                    failed_reports[checker] = rep
            if failed_reports:
                failed.append((name, context, failed_reports))

        n_total, n_failed = len(self.tests), len(failed)
        n_ok = n_total - n_failed
        if failed:
            eprint(
                f"\n{c.red}🗙{c.reset} {n_failed} test{plur(n_failed)} "
                f"ha{plur(n_failed, 've', 's')} failed:\n"
            )
            for name, context, reports in failed:
                # Format short context for inclusion in report.
                cpos = lambda cx: f"{c.grey}<{cx.position}>{c.reset}"
                eprint(f"{c.red}{name}{c.reset} {cpos(context)}")
                # Elide checkers contexts if they all are the same line
                # as previously shown context.
                last_line = context.linenum
                for checker, report in reports.items():
                    if last_line != (l := checker.context.linenum):
                        eprint(cpos(checker.context))
                    eprint(report, end="\n\n")
                    last_line = l
            eprint(
                f"{c.blue}{n_total}{c.reset} test{plur(n_total)} run: "
                f"{c.green}{n_ok}{c.reset} success{plur(n_ok, 'es')}, "
                f"{c.red}{n_failed}{c.reset} failure{plur(n_failed)}."
            )
            return False
        if n_ok:
            symbol = f"{c.green}✔"
            colon = ":"
        else:
            symbol = f"{c.yellow}??"
            colon = "?"
        print(f"\n{symbol}{c.reset} Success{colon} {n_total} test{plur(n_total)} run.")
        return True

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
            raise TestRunError(f"Cannot backup unexistent file {path}.")
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
                raise TestRunError(f"No available backup to restore file {path}.")
            else:
                # Consider the file is restored.
                return
        # TODO: try-guard the following.
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


def RunnerWrapperActor(method_name: str, name=None):
    """Create useful, trivial actors just wrapping direct calls to the Runner API.
    These actors take context as their *first* argument,
    then anything else is forwarded to the call.
    """

    wrong = False
    try:
        method = getattr(TestRunner, method_name)
        wrong = not callable(method)
    except AttributeError as e:
        wrong = True
    if wrong:
        raise SourceError(
            f"No callable method TestRunner.{method_name} "
            "to build a RunnerWrapperActor from."
        )

    # MAGIC: if a 'context' argument is expected by the method,
    # take care of not requesting it several times in Wrapper.__init__.
    method_args = getfullargspec(method).args
    try:
        n_context = method_args.index("context")
    except ValueError:
        n_context = 0  # Means none, because 0 is always self.

    class Wrapper(Actor):
        def __init__(self, context, *args, **kwargs):
            """Initialize with context + all other arguments needed
            by the wrapped TestRunner method.. EXCEPT for redundant 'context' arguments.
            """

            self.context = context
            if not n_context:
                self.args = args
            else:
                args = list(args)
                args.insert(n_context - 1, context)
                self.args = tuple(args)
            self.kwargs = kwargs

        def execute(self, runner):
            method(runner, *self.args, **self.kwargs)

    if not name:
        name = f"Runner_{method_name}_ActorWrapper"
    Wrapper.__name__ = name
    Wrapper.__qualname__ = name

    return Wrapper
