"""Gather various exceptions semantics here.
"""

# Escape codes for coloring output.
from dataclasses import dataclass


@dataclass(frozen=True)
class colors(object):
    """Common escape codes for crafting error messages."""

    grey = "\x1b[30m"
    red = "\x1b[31m"
    blue = "\x1b[34m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    reset = "\x1b[0m"


class SourceError(Exception):
    "Error in source code when extending/using the framework."
    pass


class LexError(Exception):
    """Raised by a Lexer
    (or anything aware how many input was consumed to find the error)
    to the attention of the ContextLexer
    (or anything aware of a parsing context,
    and eg. able to interpret `n_consumed` in terms of
    line/column/file/include-chain position.
    Should be upgraded into a ParseError before reaching toplevel.
    """

    def __init__(self, message, n_consumed=0):
        self.message = message
        self.n_consumed = n_consumed
        super().__init__(message)


class ParseError(Exception):
    "Error to the attention of the user, with positional context."

    def __init__(self, message, context):
        self.message = message
        self.context = context
        super().__init__(self.message)


class NoSectionMatch(Exception):
    "Raised to the parser by a reader that does not match given input."
    pass


class TestRunError(Exception):
    """Error with organisation of the runs (folders structure, shell command..),
    Typically sent by Actors and/or Checkers *after* parsing,
    with necessary information to track the problem back in the source specs files.
    All actors/checkers are expected to have `self.context` available,
    so they can leave the context to default,
    then it'll be filled by the TestRunner when catching/forwarding the error up.
    """

    __test__ = False  # Avoid being collected by Pytest.

    def __init__(self, message, context=None):
        self.message = message
        self.context = context
        super().__init__(message)


def delineate_string(s, repeat=2) -> str:
    """Find unambiguous markers to delimitate exact contours of a string.
    Useful to produce reports.
    >>> delineate_string("ah", 1)
    '<ah>'
    >>> delineate_string("ah", 2)
    '<<ah>>'
    >>> delineate_string("<ah>", 2)
    '[[<ah>]]'
    >>> delineate_string("<[ah>]", 1)
    '{<[ah>]}'
    >>> delineate_string("<[ah>]", 2)
    '{{<[ah>]}}'
    >>> delineate_string("<[a}}h>]", 1)
    '{{{<[a}}h>]}}}'
    """
    # Find a pair of opening/closing marks that do not start or end the input.
    o, c = [
        (o, c) for o, c in "<> [] {}".split() if not (s.startswith(o) or s.endswith(c))
    ][0]
    # Repeat twice to make it clear.
    (oo, cc) = (repeat * i for i in (o, c))
    # And once more for everytime it appears in the input.
    while oo in s or cc in s:
        oo += o
        cc += c
    # Well done.
    return oo + s + cc
