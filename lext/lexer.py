"""Reusable, common lexing logic, to be typically used by readers.
"""

from .exceptions import LexError

import ast
import re
import textwrap as tw


class _EOI:
    """Special singleton symbol to represent end of input in this module."""

    def __repr__(self):
        return "EOI"


EOI = _EOI()  # Only one instance allowed.


def find_python_string(input):
    r"""If the given string starts with a valid python string, parse it
    and return it along with non-consumed input and length of consumed input.
    Otherwise return None.
    >>> f = find_python_string
    >>> f("")
    >>> f(" 'test' not-a-string ") # Find first string.
    ('test', ' not-a-string ', 7)
    >>> f(" 'test' # comment") # Don't strip comments.
    ('test', ' # comment', 7)
    >>> f(r' r"raw\'" 54') # Accept any python string syntax.
    ("raw\\'", ' 54', 9)
    >>> f(" '''triple ' quoted''' \"rest") # Accept any python string syntax.
    ("triple ' quoted", ' "rest', 22)
    >>> f(" 74, id ") # Literal is not a string.
    >>> f(" not starting 'with a string'")
    >>> f(" 74 'test'") # starting with a non-string literal
    >>> f(" 'unfinished \"strings") # Not a string.
    >>> f(" not 'a'") # Resist python injection.
    """
    # Start by seeking first quote.
    first = [(q, f) for q in ('"', "'", "'''", '"""') if (f := input.find(q)) != -1]
    if not first:
        # No quotes in input.
        return None
    min = None
    quotes = None
    for q, f in first:
        if min is None or f < min:
            min = f
            quotes = [q]
        elif min == f:
            quotes.append(q)
    if len(quotes) > 1:
        # Do not confuse triple quotes like ''' for three simple quotes.
        _, quote = quotes
    else:
        (quote,) = quotes
    # Feed input with quoted chunks until it parses correctly.
    chunks = input.split(quote)
    input = chunks.pop(0) + quote
    n_consumed = len(input)
    while True:
        try:
            n = chunks.pop(0)
            input += n + (quote if chunks else "")
            n_consumed += len(n) + (len(quote) if chunks else 0)
        except IndexError:
            return None
        try:
            string = ast.literal_eval(input)
            break
        except (SyntaxError, ValueError):
            continue
    if type(string) is not str:
        # Parse succeeded but did not result in a python string.
        return None
    return string, quote.join(chunks), n_consumed


class Lexer(object):
    r"""A very naive and inefficient lexer tokenizing data on-the-fly
    and counting length of processed input.
    """

    def __init__(self, input):
        self.input = input
        self.n_consumed = 0

    @property
    def consumed(self):
        """Check for termination."""
        return not self.input

    def consume(self, n=None) -> str:
        """Return a raw read, with known number of chars, or None to consume entirely.
        >>> l = Lexer('abcdefg')
        >>> l.consume(2), l.n_consumed # Only 2.
        ('ab', 2)
        >>> l.consumed
        False
        >>> l.consume(1), l.n_consumed # Only 1.
        ('c', 3)
        >>> l.consume(0), l.n_consumed # Nothing actually.
        ('', 3)
        >>> l.consume(), l.n_consumed # All until the end.
        ('defg', 7)
        >>> l.consumed
        True
        >>> l.consume(), l.n_consumed # Again, but there is nothing left.
        ('', 7)
        >>> l.consume(0), l.n_consumed # Can read 0 after the end.
        ('', 7)
        >>> l.consume(1), l.n_consumed # But not more.
        Traceback (most recent call last):
        IndexError: Attempt to read from consumed lexer.
        """
        if n is None:
            read, self.input = self.input, ""
        elif n > len(self.input):
            raise IndexError("Attempt to read from consumed lexer.")
        else:
            read, self.input = self.input[:n], self.input[n:]
        self.n_consumed += len(read)
        return read

    def copy(self):
        """Construct a copy of the lexer.
        Useful to "fork" it when various lexing options are considered.
        """
        c = type(self)(self.input)
        c.n_consumed = self.n_consumed
        return c

    def become(self, other):
        """Drop whole state and replace with one of another lexer.
        Useful to "join" lexing when one of various lexing options has been chosen.
        """
        self.input = other.input
        self.n_consumed = other.n_consumed

    def error(self, message, backtrack=0, pos=None):
        """Convenience utility to raise error message with n_consumed inside.
        The cursor position may be corrected backwards by a non-null backtrack,
        and/or absolutely with the 'pos' argument.
        """
        pos = self.n_consumed if pos is None else pos
        raise LexError(message, pos - backtrack)

    def lstrip(self, *args, newline=True) -> "self":
        r"""Strip chars from the beginning of input.
        >>> l = Lexer(" \n begin").lstrip()
        >>> l.input, l.n_consumed
        ('begin', 3)
        >>> l = Lexer(" \n begin").lstrip(newline=False)
        >>> l.input, l.n_consumed
        ('\n begin', 1)
        """
        if newline:
            res = self.input.lstrip(*args)
            self.n_consumed += len(self.input) - len(res)
            self.input = res
        else:
            self.match(re.compile(r"[^\S\r\n]*"), consume=True)
        return self

    def match(self, token, consume=True) -> bool:
        r"""Return True if the input starts with the given token and (maybe) consume it.
        Ask for EOI to check whether no input is left.
        Ask for empty token to always match.
        Ask for a compiled re.Pattern type to match with regular expressions.
        >>> lex = Lexer(" a b c ")
        >>> l = lex.copy()
        >>> l.match('a'), l.n_consumed
        (False, 0)
        >>> l.match(''), l.n_consumed
        (True, 0)
        >>> l.lstrip().match('a', False), l.n_consumed
        (True, 1)
        >>> l.lstrip().match('a'), l.n_consumed
        (True, 2)
        >>> l.lstrip().match('b c', False), l.n_consumed
        (True, 3)
        >>> l.lstrip().match('b c'), l.n_consumed
        (True, 6)
        >>> l.match(EOI), l.n_consumed
        (False, 6)
        >>> l.lstrip().match(EOI), l.n_consumed
        (True, 7)
        >>> l.lstrip().match('X'), l.n_consumed
        (False, 7)
        >>> l.match(''), l.n_consumed
        (True, 7)
        >>> l.match(EOI), l.n_consumed
        (True, 7)

        >>> token = re.compile(r'\b[abc]\b\s+')
        >>> l = lex.copy()
        >>> l.match(token), l.n_consumed
        (False, 0)
        >>> l.lstrip().match(token), l.n_consumed
        (True, 3)
        >>> l.lstrip().match(token), l.n_consumed
        (True, 5)
        >>> l.lstrip().match(token), l.n_consumed
        (True, 7)
        >>> l.lstrip().match(token), l.n_consumed
        (False, 7)
        """
        if token is EOI:
            return not self.input
        if type(token) is re.Pattern:
            if m := token.match(self.input):
                if consume:
                    matched = m.group(0)
                    self.input = self.input.removeprefix(matched)
                    self.n_consumed += len(matched)
                return True
            return False
        if self.input.startswith(token):
            if consume:
                self.input = self.input.removeprefix(token)
                self.n_consumed += len(token)
            return True
        return False

    def find(self, token) -> bool or (bool, str or None):
        r"""Consume whitespace until the given token is found.
        Return False and consume nothing if it does not appear next in the input.
        Return also the match in case a regex is given as a token (None if nomatch).
        >>> lex = Lexer(" a b c d ")
        >>> l = lex.copy()
        >>> l.find('a'), l.n_consumed # Skip to first such token.
        (True, 2)
        >>> l.find('X'), l.n_consumed # Not found.
        (False, 2)
        >>> l.find(EOI), l.n_consumed # Not EOI yet.
        (False, 2)
        >>> l.find(' b'), l.n_consumed # Whitespace in token is ok.
        (True, 4)
        >>> l.find(''), l.n_consumed # Found immediately.
        (True, 4)
        >>> l.find('c d'), l.n_consumed
        (True, 8)
        >>> l.find(EOI), l.n_consumed # EOI is the next thing after whitespace.
        (True, 9)
        >>> l.find('X'), l.n_consumed
        (False, 9)
        >>> l.find(''), l.n_consumed
        (True, 9)
        >>> l.find(EOI), l.n_consumed
        (True, 9)

        Same tests with regex tokens.
        >>> l, rc = lex.copy(), re.compile
        >>> l.find(rc(r'a')), l.n_consumed
        ((True, 'a'), 2)
        >>> l.find(rc(r'X')), l.n_consumed
        ((False, None), 2)
        >>> l.find(rc(r'\s+b')), l.n_consumed # Whitespace in token start.
        ((True, ' b'), 4)
        >>> l.find(rc(r'')), l.n_consumed  # Found immediately.
        ((True, ''), 4)
        >>> l.find(rc(r'c[\sd]+')), l.n_consumed  # All the rest.
        ((True, 'c d '), 9)
        >>> l.find(rc(r'X')), l.n_consumed  # Nothing left..
        ((False, None), 9)
        >>> l.find(rc(r'')), l.n_consumed  # .. but emptyness.
        ((True, ''), 9)
        """
        if token == "":
            return True
        l = self.copy().lstrip()
        if token == EOI and not l.input:
            self.become(l)
            return True
        if token == EOI:
            return False
        # Watch out not to consume part of the token
        # if it's also whitespace-lstrip-able.
        if type(token) is re.Pattern:
            if (m := token.search(self.input)) is None:
                # The token is not even found.
                return (False, None)
            s, e = m.span()
            ws, rest = self.input[:s], self.input[e:]
            match = m.group(0)
        else:
            try:
                ws, rest = self.input.split(token, 1)
                match = token
            except ValueError:
                # The token is not even found.
                return False
        if ws.strip():
            # There was non-whitespace before the token.
            return (False, None) if type(token) is re.Pattern else False
        self.n_consumed += len(ws) + len(match)
        self.input = rest
        return (True, match) if type(token) is re.Pattern else True

    def find_either(self, tokens) -> str or EOI or None:
        r"""Consume whitespace until one of the given tokens is found.
        Return the longest token if several do match.
        Return None if none appears next in the input.
        >>> l = Lexer(" a :: b ")
        >>> l.find_either(['a', ':']), l.n_consumed # First wins.
        ('a', 2)
        >>> l.find_either([':', '::']), l.n_consumed # Longest wins.
        ('::', 5)
        >>> l.find_either(['X', 'Y']), l.n_consumed # None wins.
        (None, 5)
        >>> l.find_either([' b', '']), l.n_consumed # Whitespace is okay.
        (' b', 7)
        >>> l.lstrip().find_either(['', EOI]), l.n_consumed # Empty wins over EOI.
        ('', 8)
        >>> l.find_either(['X', 'Y']), l.n_consumed
        (None, 8)
        >>> l.find_either(['X', EOI]), l.n_consumed
        (EOI, 8)
        >>> l.find_either(['', EOI]), l.n_consumed
        ('', 8)

        What about regexes tokens?
        >>> l, rc = Lexer(" a :: b "), re.compile
        >>> l.find_either([rc(r'a'), ':']), l.n_consumed # First wins
        ('a', 2)
        >>> l.find_either([rc(r':+'), ':']), l.n_consumed # Longest wins (the regex)
        ('::', 5)
        >>> l.find_either([rc(r'\s+'), ' b']), l.n_consumed # Longest wins (the literal)
        (' b', 7)
        >>> l.find_either([rc(r'\s*?'), EOI]), l.n_consumed # Interacts okay with EOI.
        ('', 7)
        >>> l.find_either([EOI, rc(r'\s*')]), l.n_consumed
        (' ', 8)
        >>> l.find_either([EOI, rc(r'\s*')]), l.n_consumed
        ('', 8)
        >>> l.find_either([EOI, rc(r'\s+')]), l.n_consumed
        (EOI, 8)
        """
        # Spawn lexers to make them all 'find' then pick best one.
        longest = None
        best_lex = None
        l = self.copy()
        for token in tokens:
            if (
                (best_lex is None)
                or (longest is EOI)
                or (type(token) is re.Pattern)
                or (token is not EOI and len(longest) < len(token))
            ):
                # Search.
                if type(token) is re.Pattern:
                    found, match = l.find(token)
                else:
                    found = l.find(token)
                    match = token if found else None
                if not found:
                    continue
                # Record if best so far.
                if best_lex is None or longest is EOI or len(longest) < len(match):
                    longest = match
                    best_lex = l
                    l = self.copy()
        if best_lex is not None:
            self.become(best_lex)
            return longest
        return None

    def read_split(self) -> str:
        """Consume and return a raw (stripped) read until next whitespace.
        >>> l = Lexer(" a  b ce f ")
        >>> l.read_split(), l.n_consumed # Skips over whitespace before read.
        ('a', 2)
        >>> l.read_split(), l.n_consumed # Skips over whitespace after read.
        ('b', 5)
        >>> l.read_split(), l.n_consumed
        ('ce', 8)
        >>> l.read_split(), l.n_consumed # Finishes the input non-whitespace.
        ('f', 10)
        >>> l.read_split(), l.n_consumed # Only whitespace left.
        ('', 11)
        >>> l.read_split(), l.n_consumed # Nothing left.
        ('', 11)
        """
        s = self.input.split(None, 1)
        if len(s) == 2:
            read, _ = s
        elif len(s) == 1:
            (read,) = s
        else:
            self.lstrip()
            read = ""
        assert self.find(read)
        return read

    def read_python_string(self) -> str or None:
        r"""Find and read next python string or return None and don't consume anything.
        >>> l = Lexer(" a 'b' r'''pytho\n''' notstring")
        >>> l.read_python_string(), l.n_consumed
        (None, 0)
        >>> l.find("a"), l.n_consumed
        (True, 2)
        >>> l.read_python_string(), l.n_consumed
        ('b', 6)
        >>> l.read_python_string(), l.n_consumed
        ('pytho\n', 20)
        >>> l.read_python_string(), l.n_consumed
        (None, 20)
        >>> l.find("notstring"), l.n_consumed
        (True, 30)
        >>> l.read_python_string(), l.n_consumed
        (None, 30)
        """
        if s := find_python_string(self.input):
            string, self.input, n = s
            self.n_consumed += n
            return string
        return None

    def read_until(
        self,
        stop=EOI,
        consume_stop=True,
        strip=False,
        expect_data=None,
    ) -> str or None or (str, str):
        """Return all raw input before the fixed stop pattern.
        None if 'stop' cannot be found.
        Request EOI to return all remaining input.
        If requesting a regex pattern, the match value is also returned.
        In this case the returned value cannot be None.
        strip: True to remove whitespace padding from the read
               (note that it's still consumed).
        expect_data: Names data expected to be not empty, or backtrack and error out.
        >>> l = Lexer(" raw read <marker> another read <mark>")
        >>> l.read_until('<marker>'), l.n_consumed
        (' raw read ', 18)
        >>> l.read_until('<notfound>'), l.n_consumed
        (None, 18)
        >>> l.read_until(''), l.n_consumed
        ('', 18)
        >>> l.read_until('<mark>', False), l.n_consumed
        (' another read ', 32)
        >>> l.read_until(EOI), l.n_consumed
        ('<mark>', 38)
        >>> l.read_until(''), l.n_consumed
        ('', 38)
        >>> l.read_until(EOI), l.n_consumed
        ('', 38)
        >>> l = Lexer(" raw stripped : pear : :: : ")
        >>> l.read_until(':', strip=True), l.n_consumed
        ('raw stripped', 15)
        >>> l.read_until(':', strip=True, expect_data='fruit'), l.n_consumed
        ('pear', 22)
        >>> l.read_until(':', strip=False, expect_data='fruit'), l.n_consumed
        (' ', 24)
        >>> l.read_until(':', strip=False, expect_data='fruit')
        Traceback (most recent call last):
        lext.exceptions.LexError: Missing expected data: 'fruit'.
        >>> l.n_consumed
        24
        >>> l.read_until(':'), l.n_consumed
        ('', 25)
        >>> l.read_until(':', strip=True, expect_data='fruit'), l.n_consumed
        Traceback (most recent call last):
        lext.exceptions.LexError: Missing expected data: 'fruit'.
        >>> l.n_consumed
        25

        With regular expressions as stops.
        >>> l, rc = Lexer(" raw read <marker> another read <mark>"), re.compile
        >>> l.read_until(rc(r'<.*?>')), l.n_consumed
        ((' raw read ', '<marker>'), 18)
        >>> l.read_until(rc(r'<[uvz]+>')), l.n_consumed
        (None, 18)
        >>> l.read_until(rc(r'')), l.n_consumed
        (('', ''), 18)
        >>> l.read_until(rc(r'<.*?>'), False), l.n_consumed
        ((' another read ', '<mark>'), 32)
        >>> l.read_until(rc(r'[.*?]'), False), l.n_consumed
        (None, 32)
        >>> l.read_until(rc(r'<.*?>'), False), l.n_consumed
        (('', '<mark>'), 32)
        >>> l.read_until(rc(r'<.*?>'), True), l.n_consumed
        (('', '<mark>'), 38)
        >>> l.read_until(rc(r'<.*?>'), True), l.n_consumed
        (None, 38)
        >>> l.read_until(rc(r''), True), l.n_consumed
        (('', ''), 38)
        """
        lex = self.copy()
        if stop is EOI:
            read = lex.input
            lex.input = ""
            lex.n_consumed += len(read)
        else:
            if stop == "":
                return ""

            if type(stop) is re.Pattern:
                if (m := stop.search(lex.input)) is None:
                    return None
                s, e = m.span()
                read, lex.input = lex.input[:s], lex.input[e:]
                match = m.group(0)
            else:
                try:
                    read, lex.input = lex.input.split(stop, 1)
                    match = stop
                except ValueError:
                    return None

            lex.n_consumed += len(read)
            if consume_stop:
                lex.n_consumed += len(match)
            else:
                lex.input = match + lex.input

        if strip:
            read = read.strip()

        if expect_data is not None and not read:
            self.error(f"Missing expected data: {repr(expect_data)}.")

        self.become(lex)
        return (read, match) if type(stop) is re.Pattern else read

    def read_until_either(self, stops, *args, **kwargs) -> ("stop", str) or None:
        """Raw read until the first stop is found, and return it
        so the user knows which one it was.
        In case of ex-aequo, the longest stop matches.
        >>> l = Lexer("a b c aa bb cc u v w uu vv ww")
        >>> l.read_until_either(['b', 'cc']), l.n_consumed # First stop wins.
        (('b', 'a '), 3)
        >>> l.read_until_either(['c', 'cc']), l.n_consumed # Closest stop wins.
        (('c', ' '), 5)
        >>> l.read_until_either(['c', 'cc']), l.n_consumed # Longest stop wins.
        (('cc', ' aa bb '), 14)
        >>> l.read_until_either(['XX', 'XY']), l.n_consumed # No such stops.
        (None, 14)
        >>> l.read_until_either([]), l.n_consumed # No stops.
        (None, 14)
        >>> l.read_until_either(['', 'u']), l.n_consumed # Empty Always stops.
        (('', ''), 14)
        >>> l.read_until_either('uv'), l.n_consumed # Equivalent to ['u', 'v'].
        (('u', ' '), 16)
        >>> l.read_until_either(['uu', EOI]), l.n_consumed # Stop before EOI.
        (('uu', ' v w '), 23)
        >>> l.read_until_either(['XX', EOI]), l.n_consumed # No such stop before EOI.
        ((EOI, ' vv ww'), 29)
        >>> l.read_until_either(['afterstring']), l.n_consumed # Post-EOI vacuum.
        (None, 29)
        >>> l.read_until_either(['something', EOI]), l.n_consumed # Still budging.
        ((EOI, ''), 29)
        >>> l.read_until_either(['something', '']), l.n_consumed # Still budging.
        (('', ''), 29)

        With regular expression stops.
        >>> l, rc = Lexer("a b c aa bb cc u v w uu vv ww"), re.compile
        >>> l.read_until_either([rc(r'[bcd]'), 'cc']), l.n_consumed # First wins.
        (('b', 'a '), 3)
        >>> l.read_until_either([rc(r'c'), rc(r'c{2}')]), l.n_consumed # Closest wins.
        (('c', ' '), 5)
        >>> l.read_until_either([rc(r'c+?'), rc(r'c+')]), l.n_consumed # Longest wins.
        (('cc', ' aa bb '), 14)
        >>> l.read_until_either([rc(r'X+'), rc(r'Y')]), l.n_consumed # Not found.
        (None, 14)
        >>> l.read_until_either([rc(r''), rc(r'u')]), l.n_consumed # Empty stops.
        (('', ''), 14)
        >>> l.read_until_either([rc(r'[uv]')]), l.n_consumed # Either.
        (('u', ' '), 16)
        >>> l.read_until_either([rc(r'u+'), EOI]), l.n_consumed # Avoid EOI.
        (('uu', ' v w '), 23)
        >>> l.read_until_either([rc(r'X+'), EOI]), l.n_consumed # Can't avoid EOI.
        ((EOI, ' vv ww'), 29)
        >>> l.read_until_either([rc(r'NOTHING')]), l.n_consumed # Vacuum.
        (None, 29)
        >>> l.read_until_either([rc(r'something'), EOI]), l.n_consumed # Budging.
        ((EOI, ''), 29)
        >>> l.read_until_either([rc(r'X*'), EOI]), l.n_consumed # Budging.
        (('', ''), 29)

        Interact with stop consumption option.
        >>> l = Lexer(" before :: after ")
        >>> l.read_until_either([':', 'a'], False), l.n_consumed # Stop not consumed.
        ((':', ' before '), 8)
        >>> l.read_until_either([':', EOI], False), l.n_consumed # Blocked here then.
        ((':', ''), 8)
        >>> l.read_until_either([rc(r':'), EOI], False), l.n_consumed # Even with regs.
        ((':', ''), 8)
        >>> l.read_until_either([rc(r':+'), EOI], True), l.n_consumed # Eventually gulp.
        (('::', ''), 10)
        >>> l.read_until_either([':', EOI], True), l.n_consumed
        ((EOI, ' after '), 17)
        """
        # Find first stop.
        n_first, first = -1, None
        best_match = None
        for stop in stops:
            # Calculate index of match, if any.
            if type(stop) is re.Pattern:
                if (m := stop.search(self.input)) is None:
                    f = -1
                    match = None
                else:
                    f, _ = m.span()
                    match = m.group(0)
            elif stop is EOI:
                f = len(self.input)
                match = EOI
            else:
                f = self.input.find(stop)
                match = stop
            if (
                (n_first == -1 and f != -1)
                or (f != -1 and n_first != -1 and f < n_first)
                or (
                    f != -1
                    and f == n_first
                    and match is not EOI
                    and len(best_match) < len(match)
                )
            ):
                first = stop
                best_match = match
                n_first = f
        if n_first == -1:
            return None
        # Consume until then.
        if type(first) is re.Pattern:
            read, match = self.read_until(first, *args, **kwargs)
            return match, read
        return first, self.read_until(first, *args, **kwargs)

    def read_string_or_raw_until(
        self, stop, *args, **kwargs
    ) -> (str, bool) or None or str:
        r"""If there is a python string to parse next,
        consume it then find and consume the stop, erroring on unwanted additional data.
        Otherwise, read and return the stripped raw input until the stop.
        In addition, return True if the read was raw, False otherwise.

        consume_stop: False to stop before the matching stop.

        raw_guards: These stops are given to error out if they are found
                    before the actual stop sign in case of a raw read.

        expect_data: Names data expected to be not empty (or only whitespace)
                     in case of a raw read.
                     When provided, only the string is returned (not the boolean)
                     or None if no stop was found.

        With a string.
        >>> l, rc = Lexer("  'string' :: next"), re.compile
        >>> c = l.copy()
        >>> c.read_string_or_raw_until('::'), c.n_consumed
        (('string', False), 13)
        >>> c = l.copy()
        >>> c.read_string_or_raw_until(rc(r':+'), consume_stop=False), c.n_consumed
        (('string', False), 11)

        With raw data.
        >>> l = Lexer("  'raw\" :: next")
        >>> c = l.copy()
        >>> c.read_string_or_raw_until('::'), c.n_consumed
        (('\'raw"', True), 10)
        >>> c = l.copy()
        >>> c.read_string_or_raw_until('::', consume_stop=False), c.n_consumed
        (('\'raw"', True), 8)

        Without a stop.
        >>> l = Lexer("  'raw <nomark> next")
        >>> l.read_string_or_raw_until('::'), l.n_consumed
        (None, 0)
        >>> l.read_string_or_raw_until(rc(r':+')), l.n_consumed
        (None, 0)

        Until EOF.
        >>> l = Lexer("  'string'  ")
        >>> l.read_string_or_raw_until(EOI), l.n_consumed
        (('string', False), 12)
        >>> l = Lexer("  'raw  ")
        >>> l.read_string_or_raw_until(EOI), l.n_consumed
        (("'raw", True), 8)

        Drop the 'raw' information when expecting particular data.
        >>> l = Lexer("  'pear' :: ")
        >>> l.read_string_or_raw_until('::', expect_data='fruit'), l.n_consumed
        ('pear', 11)
        >>> l = Lexer("  pear :: ")
        >>> l.read_string_or_raw_until(rc(r':+'), expect_data='fruit'), l.n_consumed
        ('pear', 9)
        >>> l = Lexer("  ' pear ' :: ")
        >>> l.read_string_or_raw_until('::', expect_data='fruit'), l.n_consumed
        (' pear ', 13)
        >>> l = Lexer("   :: ") # No fruit.
        >>> l.read_string_or_raw_until(rc(r':+'), expect_data='fruit')
        Traceback (most recent call last):
        lext.exceptions.LexError: Missing expected data: 'fruit'.
        >>> l = Lexer(" '  ' :: ") # Explicit blank fruit.
        >>> l.read_string_or_raw_until('::', expect_data='fruit'), l.n_consumed
        ('  ', 8)
        >>> l = Lexer(" '' :: ") # Explicit empty fruit.
        >>> l.read_string_or_raw_until(rc(r':+'), expect_data='fruit'), l.n_consumed
        ('', 6)

        With unwanted data.
        >>> l = Lexer("  'string' unwanted :: next")
        >>> l.read_string_or_raw_until("::")
        Traceback (most recent call last):
        lext.exceptions.LexError: Unexpected data found between string and '::': 'unwanted'.

        >>> l = Lexer(" unwanted 'string'")
        >>> l.read_string_or_raw_until(EOI)
        Traceback (most recent call last):
        lext.exceptions.LexError: Unexpected data found before string: 'unwanted'.

        This triggers anytime the remaining raw data would partially parse as a string.
        >>> l = Lexer(" unwanted '''string \'''\"")
        >>> l.read_string_or_raw_until(EOI)
        Traceback (most recent call last):
        lext.exceptions.LexError: Unexpected data found before string: 'unwanted'.

        >>> l = Lexer("  'string''again' :: next")
        >>> l.read_string_or_raw_until(rc(r':+'))
        Traceback (most recent call last):
        lext.exceptions.LexError: Unexpected data found between string and '::': "'again'".

        >>> l = Lexer("  'string' 'more")
        >>> l.read_string_or_raw_until(EOI) # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        lext.exceptions.LexError: Unexpected data found
                                  between string and end of input: "'more".

        Overflowing stop marks with unclosed strings.
        >>> l = Lexer(" 'unclosed string :: ne'xt")
        >>> l.read_string_or_raw_until('::'), l.n_consumed
        (None, 0)

        Use guards to not overflow with raw reads.
        >>> l = Lexer(" '''multiline string\n without a need for a guard''' \n :: next")
        >>> l.read_string_or_raw_until(rc(r':+')), l.n_consumed
        (('multiline string\n without a need for a guard', False), 56)

        >>> l = Lexer(" multiline raw read\n not matching because of guards \n :: next")
        >>> l.read_string_or_raw_until('::'), l.n_consumed
        (None, 0)
        >>> l = Lexer(" override guards \n to make this read \n :: next")
        >>> l.read_string_or_raw_until(rc(r':+'), raw_guards=[]), l.n_consumed
        (('override guards \n to make this read', True), 41)
        """
        if (r := self.read_string_or_raw_until_either([stop], *args, **kwargs)) is None:
            return None
        try:
            return r[1], r[2]
        except IndexError:
            return r[1]

    def read_string_or_raw_until_either(
        self,
        stops,
        raw_guards=["\n"],
        consume_stop=True,
        expect_data=None,
    ) -> ("stop", str, bool) or None or ("stop", str):
        """Same that read_string_or_raw_until,
        but defer to `read_until_either` instead of `read_until`.
        >>> l, rc = Lexer("  'string' :: next"), re.compile
        >>> l.read_string_or_raw_until_either(['--', rc(r'nosuchstop')]), l.n_consumed
        (None, 0)
        >>> l.read_string_or_raw_until_either(['::', EOI]), l.n_consumed
        (('::', 'string', False), 13)

        >>> l.read_string_or_raw_until_either([rc(r':+'), EOI]), l.n_consumed
        ((EOI, 'next', True), 18)

        >>> l.read_string_or_raw_until_either(['::', rc(r'-+')]), l.n_consumed # Noleft.
        (None, 18)
        """
        # Use a copy to backtrack if needed.
        lex = self.copy()
        if (read := lex.read_python_string()) is not None:
            # Check for absence of data until the stop signal.
            bef = lex.n_consumed
            if (r := lex.read_until_either(stops, consume_stop)) is None:
                # That's a nomatch: backtrack.
                return None
            stop, n = r
            if notblank := n.strip():
                lex.error(
                    "Unexpected data found between string and "
                    f"{repr(stop) if stop is not EOI else 'end of input'}: "
                    f"{repr(notblank)}.",
                    pos=bef + len(n) - len(n.lstrip()),
                )
            # Commit to this lexing.
            self.become(lex)
            return (stop, read, False) if expect_data is None else (stop, read)
        if (r := lex.read_until_either(stops + raw_guards, consume_stop)) is None or (
            r[0] not in stops and r[0] in raw_guards
        ):
            return None
        stop, read = r
        # This read could actually contain unwanted data *then* a python string.
        # Only consider it's raw if we could not parse a string within it.
        l = Lexer(read)
        while True:
            if (r := l.read_until_either(['"', "'"], False)) is None:
                break
            q, b = r
            if l.read_python_string() is None:
                l.match(q)
                continue
            else:
                self.lstrip()
                self.error(f"Unexpected data found before string: {repr(b.strip())}.")
        self.become(lex)
        if not (read := read.strip()) and expect_data is not None:
            self.error(
                f"Missing expected data: {repr(expect_data)}.",
                (len(stop) if stop is not EOI else 0) + len(read.lstrip()),
            )
        return (stop, read, True) if expect_data is None else (stop, read)

    def read_tuple(self, n=[], optional=False) -> str or (str,) or None:
        r"""Read and consume comma-separated raw or quoted strings within parentheses.
        Compare number of results to expectations (n)
        to raise appropriate error if needed.
        n=[] means any number.
        Python-like unary tuples must end with a comma to not be unpacked.
        If 'optional' is set, return None if no opening parenthesis is found.
        >>> l = Lexer(" (raw read) ")
        >>> l.read_tuple(), l.n_consumed
        ('raw read', 11)
        >>> Lexer(''' (don't bother with unmatched quotes) ''').read_tuple()
        "don't bother with unmatched quotes"
        >>> Lexer(''' ("but don't neglect quoting (all) if it isn't unambiguous") ''').read_tuple()
        "but don't neglect quoting (all) if it isn't unambiguous"

        >>> Lexer(" (read, three, 'nice, (nice) values') ").read_tuple()
        ('read', 'three', 'nice, (nice) values')
        >>> Lexer(" (two with, closing comma, ) ").read_tuple()
        ('two with', 'closing comma')
        >>> Lexer(" (singleton tuple,) ").read_tuple()
        ('singleton tuple',)
        >>> (l:=Lexer(" (unpacked) ")).read_tuple(), l.n_consumed
        ('unpacked', 11)
        >>> (l:=Lexer(" () ")).read_tuple(), l.n_consumed # Empty tuple.
        ((), 3)
        >>> (l:=Lexer(" () ")).read_tuple(0), l.n_consumed # Empty may be expected.
        ((), 3)
        >>> (l:=Lexer(" ('') ")).read_tuple(), l.n_consumed # Explicit empty string.
        ('', 5)
        >>> (l:=Lexer(" ('',) ")).read_tuple(), l.n_consumed # Explicit empty string.
        (('',), 6)
        >>> (l:=Lexer(" ('', '') ")).read_tuple(), l.n_consumed # Explicit empty strings.
        (('', ''), 9)
        >>> (l:=Lexer(" (, '') ")).read_tuple(), l.n_consumed # Implicit empty string.
        (('', ''), 7)
        >>> (l:=Lexer(" (,) ")).read_tuple(), l.n_consumed # Implicit empty string.
        (('',), 4)
        >>> (l:=Lexer(" (,,) ")).read_tuple(), l.n_consumed # Implicit empty strings.
        (('', ''), 5)
        >>> (l:=Lexer(" (a,,) ")).read_tuple(), l.n_consumed # Implicit empty string.
        (('a', ''), 6)

        Auto-unpack if exactly 1 is expected.
        >>> (l:=Lexer(" (a) ")).read_tuple(1), l.n_consumed
        ('a', 4)
        >>> (l:=Lexer(" (a,) ")).read_tuple(1), l.n_consumed
        ('a', 5)
        >>> (l:=Lexer(" (a,) ")).read_tuple([1, 2]), l.n_consumed # No unpack.
        (('a',), 5)
        >>> (l:=Lexer(" (a) ")).read_tuple([1, 2]), l.n_consumed # No unpack.
        (('a',), 4)
        >>> (l:=Lexer(" (a) ")).read_tuple([0, 1]), l.n_consumed # No unpack.
        (('a',), 4)
        >>> (l:=Lexer(" () ")).read_tuple([0, 1]), l.n_consumed # No unpack.
        ((), 3)

        Check for parentheses closing and read consistency.
        >>> l = Lexer(" no opening) ")
        >>> l.read_tuple()
        Traceback (most recent call last):
        lext.exceptions.LexError: Missing opening parenthesis.
        >>> l.n_consumed
        0
        >>> l.read_tuple(optional=True) # No error in case we were expecting maybe-none.
        >>> l.n_consumed
        0
        >>> l = Lexer(" (no closing ")
        >>> l.read_tuple()
        Traceback (most recent call last):
        lext.exceptions.LexError: Missing comma in tuple or unmatched parenthesis.
        >>> l.n_consumed
        0
        >>> l = Lexer(" (no, closing \n too late) ")
        >>> l.read_tuple()
        Traceback (most recent call last):
        lext.exceptions.LexError: Missing comma in tuple or unmatched parenthesis.
        >>> l.n_consumed
        0
        >>> l = Lexer(" (not, 'all' well-quoted) ")
        >>> l.read_tuple()
        Traceback (most recent call last):
        lext.exceptions.LexError: ...
        >>> l.n_consumed
        0
        >>> l = Lexer(" (wrong, number) ")
        >>> l.read_tuple(3) # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        lext.exceptions.LexError: Expected 3 values in tuple,
                                  found 2 instead: ('wrong', 'number').
        >>> l.n_consumed
        0
        >>> l = Lexer(" (wrong, number) ")
        >>> l.read_tuple([3, 4, 5]) # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        lext.exceptions.LexError: Expected either 3, 4 or 5 values in tuple,
                                  found 2 instead: ('wrong', 'number').
        >>> l.n_consumed
        0
        >>> l = Lexer(" (wrong, number) ")
        >>> l.read_tuple([3, 4, 5]) # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        lext.exceptions.LexError: Expected either 3, 4 or 5 values in tuple,
                                  found 2 instead: ('wrong', 'number').
        >>> l.n_consumed
        0
        >>> l = Lexer(" (wrong, number) ")
        >>> l.read_tuple([3, 1]) # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        lext.exceptions.LexError: Expected either 3 or 1 value in tuple,
                                  found 2 instead: ('wrong', 'number').
        >>> l.n_consumed
        0
        """
        if type(n) is not list:
            n = [n]
        lex = self.copy()
        opening = lex.lstrip().n_consumed
        if not lex.match("("):
            lex.lstrip()
            if optional:
                return None
            lex.error("Missing opening parenthesis.")
        stop = "("
        reads = []
        while stop != ")":
            if (r := lex.read_string_or_raw_until_either([",", ")"])) is None:
                lex.error(
                    "Missing comma in tuple or unmatched parenthesis.",
                    pos=opening,
                )
            stop, read, raw = r
            reads.append(read)
        closing = lex.n_consumed - 1
        if raw and not read:
            # The last read was actually just a closing comma or empty tuple.
            reads.pop(-1)
        reads = tuple(reads)
        if n and len(reads) not in n:
            if len(n) == 1:
                exp = str(n[0])
            else:
                exp = f"either {', '.join(str(n) for n in n[:-1])} or {n[-1]}"
            s = "s" if n[-1] > 1 else ""
            lex.error(
                f"Expected {exp} value{s} in tuple, "
                f"found {len(reads)} instead: {reads}.",
                pos=closing,
            )
        self.become(lex)
        if (len(reads) == 1) and (n == [1] or ((not (raw and not read)) and n == [])):
            # Unpack singleton.
            return reads[0]
        return reads

    line_stops = ["\n", EOI]

    def read_line(self, comment_signs=["#"], strip=True, **kwargs) -> str:
        r"""Raw read until first comment sign is found, or EOL or EOI.
        >>> (l:=Lexer("  raw-read this line # not this comment ")).read_line(), l.n_consumed
        ('raw-read this line', 40)
        >>> (l:=Lexer("   # c ")).read_line(), l.n_consumed
        ('', 7)
        >>> (l:=Lexer("   # c ")).read_line(strip=False), l.n_consumed
        ('   ', 7)
        >>> (l:=Lexer("   # c ")).read_line(expect_data='anything')
        Traceback (most recent call last):
        lext.exceptions.LexError: Missing expected data: 'anything'.
        >>> l.n_consumed
        0
        >>> (l:=Lexer(" without a comment \n next")).read_line(), l.n_consumed
        ('without a comment', 20)
        >>> (l:=Lexer("  \n with a blank line")).read_line(), l.n_consumed
        ('', 3)
        >>> (l:=Lexer("\n with an empty line")).read_line(), l.n_consumed
        ('', 1)
        >>> (l:=Lexer("  \n with a blank line")).read_line(expect_data='anything')
        Traceback (most recent call last):
        lext.exceptions.LexError: Missing expected data: 'anything'.
        >>> l.n_consumed
        0
        >>> (l:=Lexer("\n with an empty line")).read_line(expect_data='anything')
        Traceback (most recent call last):
        lext.exceptions.LexError: Missing expected data: 'anything'.
        >>> l.n_consumed
        0
        """
        stop, read = self.read_until_either(
            comment_signs + self.line_stops, strip=strip, **kwargs
        )
        if stop in comment_signs:
            # Consume and ignore anything after the sign.
            _ = self.read_until_either(self.line_stops)
        return read

    def read_string_or_raw_line(
        self, comment_signs=["#"], **kwargs
    ) -> (str, bool) or str:
        r"""Like read_line, but the line may be entirely quoted.
        The returned boolean is True in case of a raw (unquoted) read.

        >>> Lexer("  raw-read this line # not this comment ").read_string_or_raw_line()
        ('raw-read this line', True)
        >>> Lexer("  'quote-read #this one' # not comment ").read_string_or_raw_line()
        ('quote-read #this one', False)
        >>> Lexer(" raw-read this line without a comment ").read_string_or_raw_line()
        ('raw-read this line without a comment', True)
        >>> Lexer(" raw-read this short line \n next line").read_string_or_raw_line()
        ('raw-read this short line', True)
        >>> Lexer("   # c ").read_string_or_raw_line()
        ('', True)
        >>> Lexer(" ''  # c ").read_string_or_raw_line()
        ('', False)
        >>> Lexer(" a # c ").read_string_or_raw_line(expect_data='anything')
        'a'
        >>> Lexer("   # c ").read_string_or_raw_line(expect_data='anything')
        Traceback (most recent call last):
        lext.exceptions.LexError: Missing expected data: 'anything'.
        >>> Lexer(" ''  # c ").read_string_or_raw_line(expect_data='anything')
        ''
        """
        r = self.read_string_or_raw_until_either(
            comment_signs + self.line_stops, **kwargs
        )
        if r[0] in comment_signs:
            # Consume and ignore anything after the sign.
            _ = self.read_until_either(self.line_stops)
        try:
            return r[1], r[2]
        except IndexError:
            return r[1]

    def find_empty_line(self, comment_signs=["#"]) -> bool:
        r"""Consume whitespace input until the end of line, dismissing possible comment.
        Return false if none is found.
        >>> l = Lexer(" # finished line \n nextline")
        >>> l.find_empty_line(), l.n_consumed
        (True, 18)
        >>> l = Lexer("  ")
        >>> l.find_empty_line(), l.n_consumed
        (True, 2)
        >>> l = Lexer("\n") # EOL
        >>> l.find_empty_line(), l.n_consumed
        (True, 1)
        >>> l = Lexer("") # EOI
        >>> l.find_empty_line(), l.n_consumed
        (True, 0)
        >>> l = Lexer(" rest # unfinished line ")
        >>> l.find_empty_line(), l.n_consumed
        (False, 0)
        >>> l = Lexer(" rest \n unfinished line ")
        >>> l.find_empty_line(), l.n_consumed
        (False, 0)
        >>> l = Lexer(" rest  ")
        >>> l.find_empty_line(), l.n_consumed
        (False, 0)
        """
        lex = self.copy()
        read = lex.read_line(comment_signs)
        if read.strip():
            return False
        self.become(lex)
        return True

    def check_empty_line(self, comment_signs=["#"]):
        r"""Consume input until the end of line,
        dismissing possible whitespace and comments.
        Raise without consuming if unexpected data is found.
        >>> (l:=Lexer(" # finished line \n nextline")).check_empty_line(), l.n_consumed
        (None, 18)
        >>> (l:=Lexer("  ")).check_empty_line(), l.n_consumed
        (None, 2)
        >>> (l:=Lexer("")).check_empty_line(), l.n_consumed
        (None, 0)
        >>> (l:=Lexer(" rest # unfinished line ")).check_empty_line()
        Traceback (most recent call last):
        lext.exceptions.LexError: Unexpected data after end of line: 'rest'.
        >>> l.n_consumed
        0
        """
        lex = self.copy()
        read = lex.read_line(comment_signs)
        if r := read.strip():
            lex.error(
                f"Unexpected data after end of line: {repr(r)}.",
                len(read),
            )
        self.become(lex)

    def read_heredoc_like(self, name="file", EOR=None, comment_signs=["#"]):
        r"""Multiline, dedented raw read delimited by the first (split) marker found.
           ······EOR # <- Anything with no whitespace inside.
            Super-verbatim read
            with newlines inside
                indentation kept
            and not*(hi'ng" par#sed at-all
            until..
        EOR # <- read terminates here.

        If the EOR marker is provided, assume it has already been consumed.

        No dedentation occurs if the marker is triangle-braced:
        ·····<EOR>
          indented with 2 spaces.  <EOR>

        >>> l = Lexer(" EOR # opening marker\n raw\n read\nEOR # closing marker")
        >>> l.read_heredoc_like(), l.n_consumed
        ('raw\nread\n', 36)

        >>> l = Lexer(" <EOR> # opening no-dedent marker\n raw\n read\n<EOR> # close")
        >>> l.read_heredoc_like(), l.n_consumed
        (' raw\n read\n', 50)

        >>> l = Lexer(" EOR # opening marker\n raw\n read\n # NO closing marker")
        >>> l.read_heredoc_like()
        Traceback (most recent call last):
        lext.exceptions.LexError: Missing closing file marker: 'EOR'.

        >>> l = Lexer(" EOR extra data\n raw\n read\nEOR # closing marker")
        >>> l.read_heredoc_like()
        Traceback (most recent call last):
        lext.exceptions.LexError: Unexpected data after end of line: 'extra data'.

        >>> Lexer(" ").read_heredoc_like()
        Traceback (most recent call last):
        lext.exceptions.LexError: Unexpected end of file when reading end-of-file marker.

        >>> l = Lexer(" marker\n already\n given EOR ")
        >>> l.read_heredoc_like(EOR='EOR'), l.n_consumed # dedentation still occurs.
        ('marker\nalready\ngiven ', 27)

        >>> l = Lexer(" marker\n already\n given <EOR> ")
        >>> l.read_heredoc_like(EOR="<EOR>"), l.n_consumed # dedentation does not occur.
        (' marker\n already\n given ', 29)
        """
        marker_known = EOR is not None
        # Find first marker.
        lex = self.copy()
        mark_lex = lex.copy()  # For possible later error message.
        if not marker_known:
            mark_lex = lex.lstrip().copy()
            if not (EOR := lex.read_split()):
                lex.error(f"Unexpected end of file when reading end-of-{name} marker.")
        # Nothing expected next on this line.
        if not marker_known:
            lex.check_empty_line(comment_signs)

        # Use it to capture all file content.
        if (read := lex.read_until(EOR)) is None:
            mark_lex.error(f"Missing closing {name} marker: {repr(EOR)}.")
        # Dedent if requested.
        if not (EOR.startswith("<") and EOR.endswith(">")):
            read = tw.dedent(read)
        self.become(lex)
        return read
