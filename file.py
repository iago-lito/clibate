from actor import Actor
from reader import Reader


class File(Actor):
    """Responsible for creating a file in the test folder."""

    def __init__(self, name, content):
        self.name = name
        self.content = content

    def execute(self, ts):
        ts.create_file(self.name, self.content)


class FileReader(Reader):
    """Hard reader using a heredoc-like marker to find the end of the match."""

    keyword = "file"

    def match(self, input):
        self.introduce(input)
        filename = self.read_parenthesized()
        self.check_double_colon()
        content = self.read_heredoc_like("file")
        actor = File(filename, content)
        return self.hard_match(actor)
