"""The RUN keyword is a basic statement to launch the command.
All output (command success or failure)
is captured by the test set for possible later checking.
As a consequence, no error or test failure is expected happen when using RUN,
"""

from actor import Actor
from reader import Reader


class Run(Actor):
    def execute(self, ts):
        ts.run_command()


class RunReader(Reader):

    keyword = "RUN"

    def match(self, input):
        self.introduce(input)
        return self.hard_match(Run())
