"""The CHECK keyword is a basic statement to run all checkers and produce test reports.

    CHECK: Name of the test being run.

"""

from actor import Actor
from reader import Reader


class Check(Actor):
    def __init__(self, name):
        self.name = name

    def execute(self, ts):
        ts.run_checks(self.name)


class CheckReader(Reader):

    keyword = "CHECK"

    def match(self, input):
        self.introduce(input)
        self.check_colon()
        name = self.read_line(expect_data="test name")
        return self.hard_match(Check(name))
