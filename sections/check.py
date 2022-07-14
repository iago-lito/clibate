"""The CHECK keyword is a basic statement to run all checkers and produce test reports.

    CHECK: Name of the test being run.

"""

from actor import Actor
from reader import Reader


class Check(Actor):
    def __init__(self, name, position):
        self.name = name
        self.position = position

    def execute(self, ts):
        ts.test_name = self.name
        ts.run_checks(self.position)


class CheckReader(Reader):

    keyword = "CHECK"

    def match(self, input, context):
        self.introduce(input)
        self.check_colon()
        name = self.read_line(expect_data="test name")
        return self.hard_match(Check(name, context.position))
