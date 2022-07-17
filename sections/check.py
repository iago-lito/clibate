"""The CHECK keyword is a basic statement to run all checkers and produce test reports.

    CHECK: Name of the test being run.

"""

from reader import Reader
from test_runner import RunnerWrapperActor


Check = RunnerWrapperActor("run_checks", "Check")


class CheckReader(Reader):

    keyword = "CHECK"

    def section_match(self, lexer):
        self.introduce(lexer)
        self.check_colon()
        name = self.read_line(expect_data="test name")
        return Check(self.keyword_context, name)
