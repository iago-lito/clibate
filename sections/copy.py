"""The Copy section brings files from the input folder to the test folder:

    copy:
        # Files may be renamed, use the arrow '->' to this end.
        input_file -> renamed_into_test_file
        path/to/input_file2 -> test_file2

        # Don't use the arrow to not rename them.
        non-renamed_file_1
        non-renamed_file_2 non-renamed_file_3 # Then several names by line is possible.

Filenames are parsed verbatim. In cases where this would breaks parsing,
quote them with python-like strings.

    copy: "ambiguous -> arrow in filename" -> r'ambiguous#commentsign' # True comment.

"""

from actor import Actor
from lexer import Lexer, EOI
from reader import Reader, MatchResult, LinesAutomaton


class Copy(Actor):
    def __init__(self, sources, targets):
        self.sources = sources
        self.targets = targets

    def execute(self, ts):
        for o, d in zip(self.sources, self.targets):
            ts.check_input_file(o)
            ts.copy_from_input(o, d)


class CopyReader(Reader):

    keyword = "copy"

    def match(self, input, _):
        self.introduce(input)
        self.check_colon()
        return self.soft_match(CopyAutomaton())


class CopyAutomaton(LinesAutomaton):
    "Constructs the Copy actor line by line."

    arrow = "->"

    def __init__(self):
        self.sources = []
        self.targets = []

    def feed(self, line, _):
        """Simple lines of the form 'source -> target' or 'filename fn name'.
        Optionally quote the files to escape exotic chars, with python string syntax.
        """
        l = Lexer(line)
        if l.find_empty_line():
            return

        if (r := l.read_string_or_raw_until(self.arrow)) is None:
            # No arrow found: interpret the line as a sequence of filenames.
            # Either all quoted or none at all (then all raw reads).
            if (name := l.read_python_string()) is None:
                names = l.read_line().split()
            else:
                names = [name]
                while (name := l.read_python_string()) is not None:
                    names.append(name)
                l.check_empty_line()
            self.sources += names
            self.targets += names
            return
        src, raw = r
        if raw and not src:
            l.error("Could not find source filename in Copy line.")
        tgt = l.read_string_or_raw_line(expect_data="destination filename")
        # Ignore anything after the comment sign.

        self.sources.append(src)
        self.targets.append(tgt)

    def terminate(self):
        return Copy(self.sources, self.targets)
