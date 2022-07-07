"""Sketch the main structure of the spec file modular parsing.
"""

from copy import CopyReader
from file import FileReader
from parser import Parser
from test_set import TestSet


if __name__ == "__main__":

    ts = TestSet("tests/input", "tests")

    spec_file = "tests/specs/test.clib"

    with open(spec_file, "r") as f:
        specs = f.read()

    parser = Parser(specs, [CopyReader(), FileReader()], filename=spec_file)

    res = parser.parse()
