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
from exceptions import TestSetError
from reader import Reader
from test_set import TestSet

from pathlib import Path


class Include(Actor):
    def __init__(self, spawn, spec_file, input_folder, section, context):
        self.spawn = spawn
        self.spec_file = spec_file
        self.input_folder = input_folder
        self.section = section
        self.context = context

    def execute(self, ts):

        blue = "\x1b[34m"
        grey = "\x1b[30m"
        reset = "\x1b[0m"

        # Search paths relatively to current one.
        c = self.context
        spec = self.spec_file
        input = self.input_folder if self.input_folder is not None else ts.input_folder
        if c.filename is None:
            parent = None
        else:
            parent = c.file_path.parent
            spec = Path(parent, self.spec_file)
            input = Path(parent, input)
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
            raise TestSetError(
                f"Missing file {self.spec_file} "
                f"to include from {parent}."
                f" ({c.position})"
            )
        if spec_path.is_dir():
            raise TestSetError(
                f"The file {self.spec_file} "
                f"to include from {parent} is a directory."
                f" ({c.position})"
            )
        # Guard against circular inclusions.
        p, pos = c.include_chain[0]
        chain = f"\n{pos} includes {grey}{p}{reset}\n which includes "
        for p, pos in c.include_chain[1:]:
            chain += f"{grey}{p}{reset} ({pos})\nwhich includes "
            if spec_path == p:
                chain += f" {grey}{spec_path}{reset} ({c.position}) again."
                raise TestSetError(f"Circular inclusion detected:{chain}.")
        if not input_path.exists():
            raise TestSetError(
                f"Missing input folder {self.input_folder} "
                f"to include from {parent}."
                f" ({c.position})"
            )
        if not input_path.is_dir():
            raise TestSetError(
                f"Input folder {self.input_folder} "
                f"to include from {parent} is not a directory."
                f" ({c.position})"
            )

        # Start this new test "section".
        if self.section:
            print(
                f"\n{blue}{self.section.rstrip('.')}{reset} "
                f"{grey}({self.spec_file}){reset}{blue}:{reset}"
            )

        # Parse instructions in this new spec file.
        instructions = c.parser.parse_file(
            self.spec_file,
            spec_path,
            c.parser.readers,
            c.include_chain + [(spec_path, c.position)],
        )

        if self.spawn:
            # Spawn a whole new, full process, but keep it nested within this one.
            new_id = ts.id + ":"  # Mark pile depth with simple piled up markers.
            new_set = TestSet(
                input_path, ts.sandbox_folder, new_id, ts.prepare_commands
            )
            new_set.setup_and_run(instructions, report=False)
            # Bring all test reports back to the original set.
            ts.tests += new_set.tests
            return

        # Otherwise, just feed them to the current test set.
        for inst in instructions:
            ts.execute(inst)


class IncludeReader(Reader):

    keyword = "include"

    def match(self, input, context):
        self.introduce(input)
        spawn = self.find("*")
        parms = self.read_tuple([1, 2])
        try:
            spec_file, input_folder = parms
        except ValueError:
            (spec_file,) = parms
            input_folder = None
        self.check_colon()
        section = self.read_line()
        return self.hard_match(
            Include(spawn, spec_file, input_folder, section, context)
        )
