class ParseEditor(object):
    """Parsed objects inheriting from this type
    are intercepted by the parser instead of being emitted.
    As they `execute()`, they can modify its state using the parser API
    before it parses subsequent input.
    This is useful to eg. integrate new readers
    read from the very target file as it is being parsed.

    To subclass:
        - implement `self.execute()`
        - make sure `self.context` is available to produce useful failure reports.

    """

    def execute(self, parser):
        """Called by the Parser with itself as an argument.
        Use the Parser API to apply the changes.
        """
        raise NotImplementedError(
            f"Missing method 'execute' for {type(self).__name__}."
        )
