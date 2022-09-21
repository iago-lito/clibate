from exceptions import NoSectionMatch, ParseError, SourceError
from lext import Lexer, Reader as LextReader, SplitAutomaton, EOI

import re


class Reader(LextReader):
    """Specialize reader for clibate purpose.
    Although in principle every subtype may rewrite everything
    and parse the spec file the way it wants,
    there are facilities here to read clibate sections with a typical-look.
    """

    def section_name(self):
        """Infer section name, assuming the reader's name is <SectionName>Reader."""
        return type(self).__name__.removesuffix("Reader")

    def attach_lexer(self, lex):
        """Entry point into the Reader's API:
        attaches the instance to self,
        so future calls don't need to pass it as an explicit argument.
        """
        self.lexer = lex

    def check_keyword(self) -> None:
        """Check that the reader's `self.keyword` is starting the match,
        Otherwise warn the calling parser with the correct exception.
        Sets `self.keyword_context` for future reference, as part of the API.
        """
        if not hasattr(self, "keyword"):
            raise SourceError(f"No 'self.keyword' defined for {type(self).__name__}.")
        # Add word boundaries to the keyword, unless already an explicit pattern.
        if type(self.keyword) is re.Pattern:
            keyword = self.keyword
        else:
            keyword = re.compile(r"\b" + self.keyword + r"\b")
        lex = self.lexer
        context = lex.context
        if not lex.match(keyword):
            raise NoSectionMatch()
        self.keyword_context = context

    def introduce(self, lex):
        """Common entrypoint both spawning the lexer and checking section keyword."""
        self.attach_lexer(lex)
        self.check_keyword()

    def check_colon(self):
        """Check that the section is correctly introduced by a colon ':'."""
        lex = self.lexer
        if not lex.find(":"):
            lex.error(f"Missing colon ':' to introduce {self.section_name()} section.")

    def check_double_colon(self):
        """Check that the section is correctly introduced by two colons '::'."""
        lex = self.lexer
        if not lex.find("::"):
            lex.error(
                "Missing double colon '::' "
                f"to introduce {self.section_name()} section."
            )

    def check_colon_type(self) -> (":" or "::"):
        """Check wether the section is introduced
        by a colon ':' (to spot soft-matchers)
        or a double colon '::' (to spot hard-matchers),
        Errors out otherwise."""
        try:
            self.check_double_colon()
            return "::"
        except ParseError:
            pass
        try:
            self.check_colon()
            return ":"
        except ParseError:
            pass
        self.lexer.error(
            "Missing colon ':' (soft-matching) or double colon '::' (hard-matching) "
            f"to introduce {self.section_name()} section."
        )


class LinesAutomaton(SplitAutomaton):
    """Soft clibate readers split their input line by line."""

    def split(self, lexer: Lexer) -> str:
        _, line = lexer.read_until_either(["\n", EOI])
        return line
