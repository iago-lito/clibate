"""The RUN keyword is a basic statement to launch the command.
All output (command success or failure)
is captured by the test set for possible later checking.
As a consequence, no error or test failure is expected happen when using RUN,

    # Example.
    RUN

"""

from actor import Actor
from reader import Reader


class Run(Actor):
    def __init__(self, position):
        self.position = position

    def execute(self, ts):
        ts.run_command(self.position)


class RunReader(Reader):

    keyword = "RUN"

    def match(self, input, context):
        self.introduce(input)
        return self.hard_match(Run(context.position))
