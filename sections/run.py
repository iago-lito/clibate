"""The RUN keyword is a basic statement to launch the command.
All output (command success or failure)
is captured by the test runner for possible later checking.
As a consequence, no error or test failure is expected happen when using RUN,

    # Example.
    RUN

"""

from reader import Reader
from test_runner import RunnerWrapperActor


Run = RunnerWrapperActor("run_command", "Run")


class RunReader(Reader):

    keyword = "RUN"

    def section_match(self, lex):
        self.introduce(lex)
        return Run(self.keyword_context)
