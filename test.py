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

    readme_extract_cleared = False
    clearing_message = False
    for (message, paths) in [
        (
            "Testing basic clibate successes.",
            ("tests/specs/main.clib", "tests/input", "tests"),
        ),
        (
            "Meta-testing clibate, including tests failures and clibate errors.",
            ("tests/meta/main.clib", "tests", "tests"),
        ),
    ]:

        print("\n{0}{1}{0}".format(" ".join(7 * "-"), message))

        specs, input, sandbox = (Path(dir, p) for p in paths)

        try:
            if error := toplevel(specs, input, sandbox):
                # Project testing failure.
                message, code = error
                print(message, file=sys.stderr)
                break
        except:
            if not readme_extract_cleared:
                print(
                    f"Expection caught while running tests, cleaning up {clib_path}..",
                    end="",
                )
                clearing_message = True
            raise
        finally:
            if not readme_extract_cleared:
                os.remove(clib_path)
                if clearing_message:
                    print(" done.")
            readme_extract_cleared = True


if __name__ == "__main__":

    # Find project tests file relatively to this script.
    dir = Path(__file__).parent

    # Crawl doctests first.
    if not pytest.main(
        [
            "--doctest-modules",
            "-x",
            str(dir),
            "-s",
            "--ignore",
            Path(dir, "tests/meta"), # Avoid recursing there.
        ]
    ):
        run_source_tests(dir)
