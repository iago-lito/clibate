# Bundle here the implementation of various common sections when using clibate.


def default_readers():
    """Construct a fresh sequence of pre-implemented readers."""
    readers = []
    for line in default_readers.types_accesses.split():
        file, name = line.split(".")
        exec(f"readers.append({name}Reader())")
    return readers


default_readers.types_accesses = "\n".join(
    """
    check.Check
    command.Command
    copy.Copy
    exit_code.ExitCode
    file.File
    include.Include
    run.Run
    success.Success
    test.Test
""".strip().split()
)


for line in default_readers.types_accesses.split():
    file, name = line.split(".")
    exec(f"from .{file} import {name}Reader")
