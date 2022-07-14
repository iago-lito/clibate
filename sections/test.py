"""The Test section just sets up the name for the next running test.

    test: Oneline name for the test.

"""

from actor import Actor
from reader import Reader


class Test(Actor):
    def __init__(self, name):
        self.name = name

    def execute(self, ts):
        ts.test_name = self.name


class TestReader(Reader):

    keyword = "test"

    def match(self, input):
        self.introduce(input)
        self.check_colon()
        name = self.read_line(expect_data="test name")
        return self.hard_match(Test(name))
