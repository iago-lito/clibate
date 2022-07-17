class Actor(object):
    """Actors are responsible for appling modifications to the test folder.

    To subclass:
        - implement `self.execute()`
        - make sure `self.context` is available to produce useful failure reports.

    """

    def __init__(self, context):
        self.context = context

    def execute(self, test_runner):
        """Called by TestRunner with itself as an argument.
        Use the TestRunner API to apply the changes.
        """
        raise NotImplementedError("Missing method 'execute' for {type(self).__name__}.")
