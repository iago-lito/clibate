#!/usr/bin/python
"""Run the clibate tests found in specifications file given as input,
with input data read from the given folder,
and within the given sandbox folder.
"""

from exceptions import TestRunError
from lext import Parser, ParseError
from lext.exceptions import colors as c
from sections import default_readers
from test_runner import TestRunner

from pathlib import Path
import argparse
import sys


def toplevel(spec, input, sandbox) -> (str, int) or None:
    """Wrap all the run it a block catching all contextualized exceptions
    resulting from a wrong spec file or a wrong organization of the tests in general.
    Unwrap them to a simple, contextualized error message + a suggested exit code.
    None means that no such bad thing was caught.
    Other exceptions reflect problems in the source code of clibate
    or its framework extensions and should pass through.
    """

    try:
        try:
            parser = Parser(default_readers())
            instructions = parser.parse_file(spec)
            rn = TestRunner(input, sandbox, parser)
            if not rn.setup_and_run(instructions):
                return "", 1
        except (ParseError, TestRunError) as e:
            if cx := e.context:
                cx = (
                    f"{c.grey}<{cx.position}>{c.reset}"
                    f"\n{cx.backwards_include_chain}"
                )
            else:
                cx = f"{c.grey}<toplevel context>{c.reset}"
            e.message = f"{e.message} {cx}"
            raise
    except ParseError as e:
        return f"{c.red}Clibate parsing error:{c.reset}\n{e.message}", 2
    except TestRunError as e:
        return f"{c.red}Error during clibate tests run:{c.reset}\n{e.message}", 3

    return None


if __name__ == "__main__":

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "spec_file",
        type=Path,
        help="Clib file specifying tests to be run.",
    )
    ap.add_argument(
        "-i",
        "--input-folder",
        type=Path,
        default=".",
        help="Folder containing input data for the tests to run against.",
    )
    ap.add_argument(
        "-s",
        "--sandbox-folder",
        type=Path,
        default=".",
        help="Folder to create temporary tests folders within.",
    )
    args = ap.parse_args()

    if error := toplevel(args.spec_file, args.input_folder, args.sandbox_folder):
        message, code = error
        print(message, file=sys.stderr)
        exit(code)
