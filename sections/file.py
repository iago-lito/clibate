"""The File section creates a file in the test folder with heredoc-like quoting.

    file (filename.ext): EOF # <- pick any marker with no whitespace inside.
        All lines here are dedented
        then introduced verbatim into the file # including comments
        # empty lines

        # and even other section's triggers because it's a hard match.
        section: will appear in `filename.ext` without breaking the parse.
    EOF

"""

from reader import Reader
from test_runner import RunnerWrapperActor


File = RunnerWrapperActor("create_file", "File")


class FileReader(Reader):

    keyword = "file"

    def section_match(self, lexer):
        self.introduce(lexer)
        filename = self.read_tuple(1)
        self.check_double_colon()
        content = self.read_heredoc_like("file")
        return File(self.keyword_context, filename, content)
