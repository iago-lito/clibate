"""The Include section permits sourcing another specification file.
Under it's starred form '*', it spawns a new test set
and feeds it from the instructions parsed there, with the same readers.
Without the star, it just feeds the instruction to the current test set,
without changing its current state.
Take this opportunity to print a delineation like a 'section' in the tests log.

    include<*> (spec_file<.clib><, input_folder>): <Optional section name.>
    #       ^                      ^^^^^^^^^^^^
    #       |                         |__: Possibly change input folder, restored after.
    #       |____________________________: Spaws a fresh new test set.

"""

from actor import Actor
from exceptions import TestRunError, colors as c
from reader import Reader
from test_runner import TestRunner

from pathlib import Path


class Include(Actor):
    def __init__(self, spawn, spec_file, input_folder, section, context):
        self.spawn = spawn
        self.spec_file = spec_file
        self.input_folder = input_folder
        self.section = section
        self.context = context

    def execute(self, rn):

        # Search paths relatively to current one.
        parent = self.context.filepath.parent
        spec = Path(parent, self.spec_file)
        ifold = self.input_folder if self.input_folder is not None else rn.input_folder
        input = Path(parent, ifold)
        spec_path, input_path = (Path(p).resolve() for p in (spec, input))

        # Attempt to append `.clib` if not present and it would help find the file.
        candidates = [spec_path]
        ext = ".clib"
        if not (n := spec_path.name).endswith(ext):
            candidates.append(spec_path.with_name(n + ext))
        spec_path = None
        for s in candidates:
            if s.exists():
                spec_path = s
                break
        if not spec_path:
            raise TestRunError(f"Missing file to include: {self.spec_file}.")
        if spec_path.is_dir():
            raise TestRunError(f"The file to include is a directory: {self.spec_file}.")

        # Guard against circular inclusions.
        inc = self.context  # Includer context: start with the one we are creating now.
        while inc:
            if spec_path == inc.filepath:
                raise TestRunError(
                    "Circular inclusion detected:\n"
                    f"{repr(str(self.context.filename))} "
                    f"includes {repr(self.spec_file)} again.",
                    self.context,
                )
            inc = inc.includer

        if not input_path.exists():
            raise TestRunError(
                f"Missing input folder {self.input_folder} "
                f"to include from {parent}."
            )
        if not input_path.is_dir():
            raise TestRunError(
                f"Input folder {self.input_folder} "
                f"to include from {parent} is not a directory."
            )

        # Start this new test "section".
        if self.section:
            print(
                f"\n{c.blue}{self.section.rstrip('.')}{c.reset} "
                f"{c.grey}({self.spec_file}){c.reset}{c.blue}:{c.reset}"
            )

        # Create new chained context and parse included file within it.
        instructions = rn.parser.parse_file(
            self.spec_file,
            path=spec_path,
            _includer_context=self.context,
        )

        if self.spawn:
            # Spawn a whole new, full process, but keep it nested within this one.
            new_id = rn.id + ":"  # Mark pile depth with simple piled up markers.
            new_set = TestRunner(
                input_path, rn.sandbox_folder, new_id, rn.prepare_commands
            )
            new_set.setup_and_run(instructions, report=False)
            # Bring all test reports back to the original set.
            rn.tests += new_set.tests
            return

        # Otherwise, just feed them to the current rn.
        for inst in instructions:
            rn.execute(inst)


class IncludeReader(Reader):

    keyword = "include"

    def section_match(self, lex):
        self.introduce(lex)
        spawn = self.find("*")
        parms = self.read_tuple([1, 2])
        try:
            spec_file, input_folder = parms
        except ValueError:
            (spec_file,) = parms
            input_folder = None
        self.check_colon()
        section = self.read_line()
        return Include(spawn, spec_file, input_folder, section, self.keyword_context)
