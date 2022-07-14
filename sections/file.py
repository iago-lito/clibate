"""The File section creates a file in the test folder with heredoc-like quoting.

    file (filename.ext): EOF # <- pick any marker with no whitespace inside.
        All lines here are dedented
        then introduced verbatim into the file # including comments
        # empty lines

        # and even other section's triggers because it's a hard match.
        section: will appear in `filename.ext` without breaking the parse.
    EOF

"""

from actor import Actor
from reader import Reader


class File(Actor):
    def __init__(self, name, content):
        self.name = name
        self.content = content

    def execute(self, ts):
        ts.create_file(self.name, self.content)


class FileReader(Reader):

    keyword = "file"

    def match(self, input, _):
        self.introduce(input)
        filename = self.read_parenthesized()
        self.check_double_colon()
        content = self.read_heredoc_like("file")
        actor = File(filename, content)
        return self.hard_match(actor)
