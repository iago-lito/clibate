"""Sketch the main structure of the spec file modular parsing.
"""

from parser import Parser
from test_set import TestSet


if __name__ == "__main__":

    ts = TestSet("tests/input", "tests")

    instructions = Parser.parse_file("tests/specs/main.clib")

    ts.setup_and_run(instructions)
