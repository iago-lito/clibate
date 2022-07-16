# Bundle here the implementation of various common sections when using clibate.

import textwrap as tw


def default_readers():
    """Construct a fresh sequence of pre-implemented readers."""
    readers = []
    for line in default_readers.types_accesses.split("\n"):
        file, name = line.split(".", 1)
        try:
            name, args = name.split(None, 1)
        except ValueError:
            args = "[()]"
        Reader = eval(f"{name}Reader")
        args = eval(args)
        for a in args:
            reader = Reader(*a)
            readers.append(reader)
    return readers


default_readers.types_accesses = tw.dedent(
    """
    check.Check
    command.Command
    copy.Copy
    exit_code.ExitCode
    expect.Expect [(True,), (False,)]
    file.File
    include.Include
    output.Output [('stdout',), ('stderr',)]
    run.Run
    test.Test
    """.strip()
)


for line in default_readers.types_accesses.split("\n"):
    file, name = line.split(".", 1)
    try:
        name, _ = name.split(None, 1)
    except ValueError:
        pass
    exec(f"from .{file} import {name}Reader")
