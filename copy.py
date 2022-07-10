from actor import Actor
from exceptions import LineFeedError
from parsing_utils import find_python_string
from reader import Reader, MatchResult, LinesAutomaton


class Copy(Actor):
    "Responsible for copying a list of files from the input folder to the test folder."

    def __init__(self, sources, targets):
        self.sources = sources
        self.targets = targets


class CopyReader(Reader):
    """Soft reader with a simple block of lines.

    copy:
        original_input_file -> name_in_test_folder
        path/to/other_file -> copy2

    """

    def match(self, input):
        # Extract one line.
        try:
            line, _ = input.split("\n", 1)
            end = len(line) + 1
        except ValueError:
            # Reached EOF.
            line = input
            end = len(line)
        if line.startswith("copy:"):
            # Ignore the rest of the line for now.
            return MatchResult(type="soft", lines_automaton=CopyAutomaton(), end=end)
        return None


def second_filename(rest):
    """Factorize common procedure in CopyAutomaton.feed,
    after the arrow has been found.
    """
    if s := find_python_string(rest):
        tgt, rest = s
        rest = rest.lstrip()
        # Only comment should remain.
        if not rest.startswith("#"):
            raise LineFeedError(f"Unexpected token(s) in Copy line: {rest}.")
    else:
        # Strip comment.
        try:
            rest, _ = rest.split("#", 1)
        except ValueError:
            pass
        tgt = rest.strip()
    return tgt


class CopyAutomaton(LinesAutomaton):
    "Constructs the Copy actor line by line."

    arrow = "->"

    def __init__(self):
        self.sources = []
        self.targets = []

    def feed(self, line):
        """Simple lines of the form 'source -> target'.
        Optionally quote the files to escape exotic chars, with python string syntax.
        """
        if s := find_python_string(line):
            src, rest = s
            rest = rest.lstrip()
            if not rest.startswith(self.arrow):
                raise LineFeedError(
                    f"Could not find arrow ({self.arrow}) in Copy line."
                )
            rest = rest.removeprefix(self.arrow)
            tgt = second_filename(rest)
        else:
            try:
                src, rest = line.split(self.arrow, 1)
            except ValueError:
                raise LineFeedError(
                    f"Could not find arrow ({self.arrow}) in Copy line."
                )
            src = src.strip()
            tgt = second_filename(rest)
        self.sources.append(src)
        self.targets.append(tgt)

    def terminate(self):
        return Copy(self.sources, self.targets)
