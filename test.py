#!/usr/bin/python
"""Test the main structure of the spec file modular parsing.
"""

from main import toplevel

from pathlib import Path
import os
import pytest
import sys


def run_source_tests(dir):

    # Extract the example clib file in the README
    # and temporarily add it to the tests folder.
    with open(Path(dir, "README.md"), "r") as file:
        file = file.read()
    _, clib = file.split("```clib", 1)
    clib, _ = clib.split("```", 1)
    clib_path = Path(dir, "tests/specs/basic_awk_from_README.clib").resolve()
    with open(clib_path, "w") as file:
        file.write(clib)

    specs = Path(dir, "tests/specs/main.clib")
    input = Path(dir, "tests/input")
    sandbox = Path(dir, "tests")

    code = 0
    try:
        if error := toplevel(specs, input, sandbox):
            # Project testing failure.
            message, code = error
            print(message, file=sys.stderr)
            raise AssertionError("Clibate testing failed.")
    except:
        code = -1
        print(
            f"Expection caught while running tests, cleaning up {clib_path}..",
            end="",
        )
        raise
    finally:
        os.remove(clib_path)
        if code:
            print(" done.")


if __name__ == "__main__":

    # Find project tests file relatively to this script.
    dir = Path(__file__).parent

    # Crawl doctests first.
    if not pytest.main(["--doctest-modules", "-x", str(dir), "-s"]):
        run_source_tests(dir)
