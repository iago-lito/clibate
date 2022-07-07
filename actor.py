class Actor(object):
    """Actors are responsible for appling modifications to the test folder."""

    def execute(self, test_set):
        """Called by TestSet with itself as an argument.
        Use the TestSet API to apply the changes.
        """
        raise NotImplementedError("Missing method 'execute' for {type(self).__name__}.")
