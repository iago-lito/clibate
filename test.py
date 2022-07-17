#!/usr/bin/python
"""Test the main structure of the spec file modular parsing.
"""

from parser import Parser
from test_set import TestSet

from pathlib import Path
import pytest
import os

if __name__ == "__main__":

    # Find project tests file relatively to this script.
    dir = Path(__file__).parent

    # Crawl doctests first.
    if code := pytest.main(["--doctest-modules", "-x", str(dir)]):
        exit(code)

    # Extract the example clib file in the README
    # and temporarily add it to the tests folder.
    with open(Path(dir, "README.md"), "r") as file:
        file = file.read()
    _, clib = file.split("```clib", 1)
    clib, _ = clib.split("```", 1)
    clib_path = Path(dir, "tests/specs/basic_awk_from_README.clib").resolve()
    with open(clib_path, "w") as file:
        file.write(clib)

    try:
        ts = TestSet(Path(dir, "tests/input"), Path(dir, "tests"))
        instructions = Parser.parse_file(Path(dir, "tests/specs/main.clib"))
        ts.setup_and_run(instructions)
    except:
        print(
            f"Expection caught while running tests, cleaning up {clib_path}..", end=""
        )
    finally:
        os.remove(clib_path)
        print(" done.")
