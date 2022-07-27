"""The Readers section permits sourcing a python file
to produce original, user-defined readers, and add/remove them from the parser
to enable/remove support for parsing subsequent sections in specification files.

    readers <(file.py)>: + MyReaderType MyOtherReaderType # (class names)
    # (the file is searched from the location of the spec file being read)

    readers: - MyReaderType # (remove if instance of the class name)

"""

from parse_editor import ParseEditor
from exceptions import ParseError, colors as c
from reader import Reader, LinesAutomaton

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReadersEdit(object):
    add: bool  # False to remove.
    type_name: str
    context: "ParseContext"


class Readers(ParseEditor):
    def __init__(self, python_file, context):
        self.python_file = python_file
        self.context = context
        # Filled by the automaton.
        self.readers = []  # [ReadersEdit]

    def execute(self, parser):
        globs = globals()
        # Source python file.
        if self.python_file:
            path = Path(self.context.filepath.parent, self.python_file).resolve()
            if not path.exists():
                raise ParseError(
                    f"Could not find reader python file {repr(self.python_file)} "
                    f"{c.grey}({repr(str(path))}){c.reset}.",
                    self.context,
                )
            with open(path) as f:
                code = compile(f.read(), path, "exec")
                exec(code, globs, globs)
        # Edit parser.
        add = []
        remove = []
        for reader in self.readers:
            if reader.add:
                add.append(reader)
            else:
                remove.append(reader)
        if add:
            new_readers = []
            for r in add:
                try:
                    r = globs[r.type_name]()
                except KeyError:
                    raise ParseError(
                        f"Reader class {repr(r.type_name)} not defined. "
                        "Has the corresponding python file been sourced?",
                        self.context,
                    )
            parser.add_readers(globs[r.type_name]() for r in add)
        if remove:
            names = [r.type_name for r in remove]
            parser.remove_readers(lambda r: type(r).__name__ in names)


class ReadersReader(Reader):

    keyword = "readers"

    def section_match(self, lex):
        self.introduce(lex)
        python_file = self.read_tuple(1, optional=True)
        self.check_colon()
        return ReadersAutomaton(python_file, self.keyword_context)


class ReadersAutomaton(LinesAutomaton):
    def __init__(self, *args, **kwargs):
        self.actor = Readers(*args, **kwargs)
        self.add = None

    def feed(self, lex):
        if lex.find_empty_line():
            return
        sign = lex.find_either(["+", "-"])
        if self.add is None and sign is None:
            lex.error("Missing sign (+ or -) before readers names.")
        self.add = sign == "+"
        while True:
            context = lex.lstrip().context
            type_name = lex.read_split()
            if not type_name:
                # Line consumed.
                return
            self.actor.readers.append(ReadersEdit(self.add, type_name, context))

    def terminate(self):
        if not self.actor.readers:
            raise ParseError("Missing reader names.", self.actor.context)
        return self.actor
