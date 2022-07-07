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
