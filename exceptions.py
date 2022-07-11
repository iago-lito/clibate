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
