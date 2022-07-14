# Bundle here the implementation of various common sections when using clibate.

types_accesses = """
    check.Check
    command.Command
    copy.Copy
    exit_code.ExitCode
    file.File
    run.Run
    success.Success
    test.Test
"""

default_readers = []

for line in types_accesses.strip().split():
    file, name = line.strip().split(".")
    exec(f"from .{file} import {name}Reader")
    exec(f"default_readers.append({name}Reader())")

del types_accesses
