"""Gather various exceptions semantics here.
"""


class SourceError(Exception):
    "Error in source code when extending/using the framework."
    pass


class ParseError(Exception):
    "Error during parsing of the tests specification file."
    pass


class LineFeedError(Exception):
    "Error during line processing with a soft reader."
    pass
