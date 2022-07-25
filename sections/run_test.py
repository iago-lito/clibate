"""The RUNTEST keyword is a basic statement to run all current checkers
and produce test reports.

    RUNTEST<: Name of the test being run.>

"""

from exceptions import ParseError
from reader import Reader
from test_runner import RunnerWrapperActor

RunTest = RunnerWrapperActor("run_test", "RunTest")

class RunTestReader(Reader):

    keyword = "RUNTEST"

    def section_match(self, lexer):
        self.introduce(lexer)
        try:
            self.check_colon()
        except ParseError:
            # Use current test name.
            name = None
            self.check_empty_line()
        else:
            name = self.read_line(expect_data="test name")
        return RunTest(self.keyword_context, name)
