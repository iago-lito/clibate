#!/usr/bin/python
"""Run the clibate tests found in specifications file given as input,
with input data read from the given folder,
and within the given sandbox folder.
"""

from parser import Parser
from test_set import TestSet

from pathlib import Path
import argparse

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

    ts = TestSet(args.input_folder, args.sandbox_folder)
    instructions = Parser.parse_file(args.spec_file)
    ts.setup_and_run(instructions)

