"""Gather various exceptions semantics here.
"""


class SourceError(Exception):
    "Error in source code when extending/using the framework."
    pass


class ParseError(Exception):
    "Error during parsing of the tests specification file."

    def __init__(self, message, n_consumed=0):
        """Create with an error message, and the number of characters consumed
        when the error happened.
        """
        self.n_consumed = n_consumed
        self.message = message
        super().__init__(message)


class NoSectionMatch(Exception):
    "Raised to the parser by a reader that does not match given input."
    pass


class TestSetError(Exception):
    "Error with organisation of the runs (folders structure, shell command..)"
    __test__ = False  # Avoid being collected by Pytest.
    pass


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
