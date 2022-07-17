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
from reader import Reader, LinesAutomaton


class Copy(Actor):
    def __init__(self):
        # Filled up during parsing.
        self.context = None  # (and this one during 'execute').
        self.sources = []
        self.targets = []
        self.contexts = []

    def execute(self, rn):
        for src, tgt, cx in zip(self.sources, self.targets, self.contexts):
            # Set up temporary context so the runner grabs the good on in case of error.
            self.context = cx
            rn.check_input_file(src)
            rn.copy_from_input(src, tgt)


class CopyReader(Reader):

    keyword = "copy"

    def section_match(self, lexer):
        self.introduce(lexer)
        self.check_colon()
        return CopyAutomaton()


class CopyAutomaton(LinesAutomaton):
    "Constructs the Copy actor line by line."

    arrow = "->"

    def __init__(self):
        self.actor = Copy()

    def feed(self, lex):
        """Simple lines of the form 'source -> target' or 'filename fname name'.
        Optionally quote the files to escape exotic chars, with python string syntax.
        """
        context = lex.context
        if lex.find_empty_line():
            return

        arrow_cx = lex.lstrip().context
        if (pre_arrow := lex.read_string_or_raw_until(self.arrow)) is None:
            # No arrow found: interpret the line as a sequence of filenames.
            # Either all quoted or none at all (then all raw reads).
            if (name := lex.read_python_string()) is not None:
                names = [name]
                while (name := lex.read_python_string()) is not None:
                    names.append(name)
                lex.check_empty_line()
            else:
                names = lex.consume().split()
            self.actor.sources += names
            self.actor.targets += names
            self.actor.contexts += len(names) * [context]
            return
        src, raw = pre_arrow
        if raw and not src:
            lex.error(
                f"Missing source filename "
                f"before {repr(self.arrow)} arrow in copy line.",
                context=arrow_cx,
            )
        tgt = lex.read_string_or_raw_line(expect_data="target filename")
        # Ignore anything after the comment sign.
        self.actor.sources.append(src)
        self.actor.targets.append(tgt)
        self.actor.contexts.append(context)

    def terminate(self):
        return self.actor
