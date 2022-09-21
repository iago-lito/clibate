"""Ignore blank lines and pure comment lines.
"""

from exceptions import NoSectionMatch
from reader import Reader


class IgnoredReader(Reader):
    def section_match(self, lexer):
        if lexer.find_empty_line():
            return None
        raise NoSectionMatch
