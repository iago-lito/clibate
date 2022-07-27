class ParseEditor(object):
    """Instead of being passed to the test runner,
    ParseEditor objects are directly called back by the parser
    to modify its state before parsing subsequent input.
    This is useful to eg. integrate new readers
    while test specifications are being parsed.

    To subclass:
        - implement `self.execute()`
        - make sure `self.context` is available to produce useful failure reports.

    """

    def execute(self, parser):
        """Called by the Parser with itself as an argument.
        Use the Parser API to apply the changes.
        """
        raise NotImplementedError("Missing method 'execute' for {type(self).__name__}.")
