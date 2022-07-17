#!/usr/bin/python
"""Test the main structure of the spec file modular parsing.
"""

from parser import Parser
from test_set import TestSet

from pathlib import Path
import pytest

if __name__ == "__main__":

    # Find project tests file relatively to this script.
    dir = Path(__file__).parent

    # Crawl doctests first.
    if code := pytest.main(["--doctest-modules", "-x", str(dir)]):
        exit(code)

    ts = TestSet(Path(dir, "tests/input"), Path(dir, "tests"))

    instructions = Parser.parse_file(Path(dir, "tests/specs/main.clib"))

    ts.setup_and_run(instructions)
