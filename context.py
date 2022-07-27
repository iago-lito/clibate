"""Wraps a basic lexer with additional contextual information
regarding the file currently being run, the position within it in terms of line/column
and the include chain.
This is the actual lexer handed out to readers during parsing.
All calls to the base lexer are deferred to it,
but ParseError exceptions are caught to append additional useful information
before they are raised again, or exit the program with a graceful error message
instead of a python traceback.
"""

from exceptions import LexError, ParseError, colors as c
from lexer import Lexer, EOI  # Reexport EOI.

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class ParseContext(object):
    """Immutable object containing all necessary information
    to locate one problem in a sourced spec file.
    """

    filename: str  # As input by user.
    filepath: Path  # Canonicalized.
    parser: "Parser"
    includer: "ParseContext" = None  # Chain inclusions up to root context.
    linenum: int = 1
    colnum: int = 1

    @property
    def path(self) -> str:
        return str(self.filepath)

    @property
    def linecol(self) -> str:
        return f"{self.linenum}:{self.colnum}"

    @property
    def position(self) -> str:
        return f"{self.filename}:{self.linecol}"

    @property
    def backwards_include_chain(self) -> str:
        message = f"{c.grey}{self.path}{c.reset}"
        inc = self.includer
        while inc is not None:
            message += f"\nincluded from {c.grey}{inc.path}:{inc.linecol}{c.reset}"
            inc = inc.includer
        return message


# Useful for testing.
MOCK_CONTEXT = ParseContext("<mock_context>", None, None, None)


class ContextLexer(object):
    """Wraps a lexer object with all additional information needed
    to produce a correct ParseContext on-demand are raise contextualized ParseErrors.
    This is a mutable value passed to readers during parsing,
    as such, internals needs to be well-protected.
    """

    def __init__(self, input, context):
        self._lexer = Lexer(input)
        self._base_context = context
        # Make those dynamical.
        self._linenum = context.linenum
        self._colnum = context.colnum
        # Keep a late copy of the lexer to correctly update the above two numbers
        # when we're catching up with the new one.
        self._late = self._lexer.copy()

    def copy(self):
        """Mirror inner base Lexer.copy, but with whole context associated."""
        c = ContextLexer(self._lexer.input, self._base_context)
        c._lexer.n_consumed = self._lexer.n_consumed
        c._linenum = self._linenum
        c._colnum = self._colnum
        c._late.become(self._late)
        return c

    def become(self, other):
        """Mirror inner base Lexer.become, but with whole context associated."""
        self._lexer.become(other._lexer)
        self._base_context = other._base_context
        self._linenum = other._linenum
        self._colnum = other._colnum
        self._late.become(other._late)

    @property
    def context(self):
        """Emit correct current (frozen) context."""
        return ParseContext(
            self._base_context.filename,
            self._base_context.filepath,
            self._base_context.parser,
            self._base_context.includer,
            self._linenum,
            self._colnum,
        )

    def _update_position(self):
        """If the lexer has moved, update position accordingly."""
        actual_lexer = self._lexer
        late = self._late
        delta = actual_lexer.n_consumed - late.n_consumed
        if not delta:
            return
        assert delta > 0
        actual_lexer.n_consumed
        late.n_consumed
        # Count newlines in the consumed part.
        consumed = late.input[:delta]
        newlines = consumed.count("\n")
        self._linenum += newlines
        if newlines:
            self._colnum = delta - consumed.rfind("\n")
        else:
            self._colnum += delta
        # Catch up.
        late.become(actual_lexer)

    # Choose the calls to defer to the base lexer's API.
    _lexer_defer = [
        f
        for f in dir(Lexer)
        if any(f.startswith(p) for p in ("read", "find", "check", "match"))
    ] + ["consume", "lstrip"]

    @property
    def consumed(self):
        return self._lexer.consumed

    def _upgrade_lex_error_to_parse_error(self, lex_error):
        """Update internal state to match that wanted by the throwing base lexer,
        then produce adequate context.
        ASSUMPTION: this error has just been raised by self._lexer,
        and we are in the process of forwarding it up the stack.
        """
        if lex_error.n_consumed != self._lexer.n_consumed:
            # The lexer is willing to backtrack.
            # (note that we cannot backtrack further back than latest lifeline)
            delta = self._late.n_consumed - lex_error.n_consumed
            assert delta < 0
            # Backtrack to lifeline.
            self._lexer.become(self._late)
            # Consume again just what's needed
            # to get where the lexer meant to locate the error.
            self._lexer.consume(-delta)
        self._update_position()
        return ParseError(lex_error.message, self.context)

    @classmethod
    def _wrap_lexer_method(cls, method):
        """Construct a wrapping method around the base lexer's one.
        If it raises a parse error, intercept,
        bactrack it to the position specified in the exception,
        add contextual information to it then forward up.
        """

        def context_wrapped(self, *args, **kwargs):
            try:
                res = getattr(self._lexer, method)(*args, **kwargs)
            except LexError as e:
                raise self._upgrade_lex_error_to_parse_error(e) from e
            # If everything went well, consume and forward the result.
            self._update_position()
            # Unless it's supposed to be 'self'.
            if res is self._lexer:
                return self
            return res

        return context_wrapped

    def error(self, message, *args, context=None, **kwargs):
        """Wrap base lexer method, but directly upgrade to a parse error,
        overloading context if provided.
        """
        if context:
            # We may directly produce the error.
            raise ParseError(message, context)
        # First forward to lexer so it adjusts position correctly.
        try:
            self._lexer.error(message, *args, **kwargs)
        except LexError as e:
            raise self._upgrade_lex_error_to_parse_error(e) from e


for method_name in ContextLexer._lexer_defer:
    setattr(ContextLexer, method_name, ContextLexer._wrap_lexer_method(method_name))
