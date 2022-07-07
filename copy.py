from actor import Actor
from exceptions import LineFeedError
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


class CopyAutomaton(LinesAutomaton):
    "Constructs the Copy actor line by line."

    arrow = "->"

    def __init__(self):
        self.sources = []
        self.targets = []

    def feed(self, line):
        """Simple lines of the form 'source -> target'."""
        # Strip comment.
        try:
            line, _ = line.split("#", 1)
        except ValueError:
            pass
        if self.arrow in line:
            src, tgt = line.split("->", 1)
            self.sources.append(src.strip())
            self.targets.append(tgt.strip())
            return
        raise LineFeedError(f"Could not parse line as a Copy line.")

    def terminate(self):
        return Copy(self.sources, self.targets)
