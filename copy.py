from actor import Actor
from reader import Reader, MatchResult, LinesAutomaton


class Copy(Actor):
    "Responsible for copying a list of files from the input folder to the test folder."

    def __init__(self):
        self.sources = []
        self.targets = []


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

    def __init__(self):
        self.copy = Copy()
