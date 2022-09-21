from lext.exceptions import *


class SourceError(Exception):
    "Error in source code when extending/using the framework."
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
