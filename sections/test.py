"""The Test section just sets up the name for the next running test.

    test: Oneline name for the test.

"""

from reader import Reader
from test_runner import RunnerWrapperActor

TestName = RunnerWrapperActor("update_test_name", "TestName")


class TestReader(Reader):

    keyword = "test"

    def section_match(self, lex):
        self.introduce(lex)
        self.check_colon()
        name = self.read_line(expect_data="test name")
        return TestName(self.keyword_context, name)
