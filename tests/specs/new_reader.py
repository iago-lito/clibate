from checker import Checker
from reader import Reader


class NewChecker(Checker):
    """Dummy checker to just spot a NEW keyword within output."""

    expecting_stdout = True

    def check(self, _rn, _, stdout, __):
        output = stdout.decode('utf-8')
        if "NEW" in output:
            return None
        return "No NEW keyword found in output."


class NewReader(Reader):

    keyword = "new-reader"

    def section_match(self, lexer):
        self.introduce(lexer)
        return NewChecker(self.keyword_context)
