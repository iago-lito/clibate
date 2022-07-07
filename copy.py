from actor import Actor
from lexer import Lexer, EOI
from reader import Reader, MatchResult, LinesAutomaton


class Copy(Actor):
    "Responsible for copying a list of files from the input folder to the test folder."

    def __init__(self, sources, targets):
        self.sources = sources
        self.targets = targets

    def execute(self, ts):
        for o, d in zip(self.sources, self.targets):
            ts.check_input_file(o)
            ts.copy_from_input(o, d)


class CopyReader(Reader):
    """Soft reader with a simple block of lines.

    copy:
        original_input_file -> name_in_test_folder
        path/to/other_file -> copy2

    """

    keyword = "copy"

    def match(self, input):
        self.introduce(input)
        self.check_colon()
        return self.soft_match(CopyAutomaton())


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
        l = Lexer(line).lstrip()
        # Dismiss empty/comment lines.
        if not l.input or l.match("#"):
            return

        n = l.n_consumed
        if (r := l.read_string_or_raw_until(self.arrow)) is None:
            l.error(f"Could not find arrow ({self.arrow}) in Copy line.")
        src, raw = r
        if raw and not src:
            l.error("Could not find source filename in Copy line.", pos=n)
        _, tgt, raw = l.read_string_or_raw_until_either(["#", EOI])
        if raw and not tgt:
            l.error("Could not find destination filename in Copy line.")
        # Ignore anything after the comment sign.

        self.sources.append(src)
        self.targets.append(tgt)

    def terminate(self):
        return Copy(self.sources, self.targets)
