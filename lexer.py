"""Reusable, common lexing logic, to be typically used by readers parsing the spec file.
"""

from exceptions import ParseError

import ast


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

    def copy(self):
        """Construct a copy of the lexer.
        Useful to "fork" it when various lexing options are considered.
        """
        c = type(self)(self.input)
        c.n_consumed = self.n_consumed
        return c

    def become(self, other):
        """Drop whole state a replace with one of another lexer.
        Useful to "join" lexing when one of various lexing options has been chosen.
        """
        self.input = other.input
        self.n_consumed = other.n_consumed

    def error(self, message, backtrack=0, pos=None):
        """Convenience utility to raise error message with n_consumed inside.
        The cursor position my be corrected backwards by a non-null backtrack
        """
        pos = self.n_consumed if pos is None else pos
        raise ParseError(message, pos - backtrack)

    def lstrip(self, *args) -> "self":
        """Strip chars from the beginning of input.
        >>> l = Lexer("  begin").lstrip()
        >>> l.input, l.n_consumed
        ('begin', 2)
        """
        res = self.input.lstrip(*args)
        self.n_consumed += len(self.input) - len(res)
        self.input = res
        return self

    def match(self, token) -> bool:
        """Return True if the input starts with the given token and consume it.
        Ask for EOI to check whether no input is left.
        Ask for empty token to always match.
        >>> l = Lexer(" a b c ")
        >>> l.match('a'), l.n_consumed
        (False, 0)
        >>> l.match(''), l.n_consumed
        (True, 0)
        >>> l.lstrip().match('a'), l.n_consumed
        (True, 2)
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
        """
        if token is EOI:
            return not self.input
        if self.input.startswith(token):
            self.input = self.input.removeprefix(token)
            self.n_consumed += len(token)
            return True
        return False

    def find(self, token) -> bool:
        """Consume whitespace until the given token is found.
        Return False and consume nothing if it does not appear next in the input.
        >>> l = Lexer(" a b c d ")
        >>> l.find('a'), l.n_consumed # Skip to first such token.
        (True, 2)
        >>> l.find('X'), l.n_consumed # Not found.
        (False, 2)
        >>> l.find(EOI), l.n_consumed # Not EOI yet.
        (False, 2)
        >>> l.find(' b'), l.n_consumed # Whitespace in token is ok.
        (True, 4)
        >>> l.find(''), l.n_consumed # Equivalent to l.lstrip()
        (True, 5)
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
        """
        l = self.copy().lstrip()
        if token == "" or (token == EOI and not l.input):
            self.become(l)
            return True
        if token == EOI:
            return False
        # Watch out not to consume part of the token
        # if it's also whitespace-lstrip-able.
        try:
            ws, rest = self.input.split(token, 1)
        except ValueError:
            # The token does not occur.
            return False
        if ws.strip():
            # There was non-whitespace before the token.
            return False
        self.n_consumed += len(ws) + len(token)
        self.input = rest
        return True

    def find_either(self, tokens) -> str or EOI or None:
        """Consume whitespace until one of the given tokens is found.
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
        >>> l.find_either(['', EOI]), l.n_consumed # Empty wins over EOI.
        ('', 8)
        >>> l.find_either(['X', 'Y']), l.n_consumed
        (None, 8)
        >>> l.find_either(['X', EOI]), l.n_consumed
        (EOI, 8)
        >>> l.find_either(['', EOI]), l.n_consumed
        ('', 8)
        """
        # Spawn lexers to make them all 'find' then pick best one.
        longest = None
        best_lex = None
        l = self.copy()
        for token in tokens:
            if (
                (best_lex is None)
                or (longest is EOI)
                or (token is not EOI and len(longest) < len(token))
            ):
                if l.find(token):
                    longest = token
                    best_lex = l
                    l = self.copy()
        if best_lex is not None:
            self.become(best_lex)
            return longest
        return None

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

    def read_until(self, stop=EOI, consume_stop=True) -> str or None:
        """Return all raw input before the fixed stop pattern.
        None if 'stop' cannot be found.
        Request EOI to return all remaining input.
        In this case the returned value cannot be None.
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
        """
        if stop is EOI:
            read = self.input
            self.input = ""
            self.n_consumed += len(read)
            return read
        if stop == "":
            return ""
        try:
            read, self.input = self.input.split(stop, 1)
        except ValueError:
            return None
        self.n_consumed += len(read)
        if consume_stop:
            self.n_consumed += len(stop)
        else:
            self.input = stop + self.input
        return read

    def read_until_either(self, stops, consume_stop=True) -> ("stop", str) or None:
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

        Interact with stop consumption option.
        >>> l = Lexer(" before : after ")
        >>> l.read_until_either([':', 'a'], False), l.n_consumed # Stop not consumed.
        ((':', ' before '), 8)
        >>> l.read_until_either([':', EOI], False), l.n_consumed # Blocked here then.
        ((':', ''), 8)
        >>> l.read_until_either([':', EOI], True), l.n_consumed # Eventually consume.
        ((':', ''), 9)
        >>> l.read_until_either([':', EOI], True), l.n_consumed
        ((EOI, ' after '), 16)
        """
        # Find first stop.
        n_first, first = -1, None
        for stop in stops:
            f = self.input.find(stop) if stop is not EOI else len(self.input)
            if (
                (n_first == -1 and f != -1)
                or (f != -1 and n_first != -1 and f < n_first)
                or (f != -1 and f == n_first and len(first) < len(stop))
            ):
                first = stop
                n_first = f
        if n_first == -1:
            # None found.
            return None
        # Consume until then.
        return first, self.read_until(first, consume_stop)

    def read_string_or_raw_until(self, stop, *args, **kwargs) -> (str, bool) or None:
        r"""If there is a python string to parse next,
        consume it then find and consume the stop, erroring on unwanted additional data.
        Otherwise, read and return the stripped raw input until the stop.
        In addition, return True if the read was raw, False otherwise.
        raw_guards stops are given to error out if they are found
        before the actual stop sign in case of a raw read.

        With a string.
        >>> l = Lexer("  'string' :: next")
        >>> c = l.copy()
        >>> c.read_string_or_raw_until('::'), c.n_consumed
        (('string', False), 13)
        >>> c = l.copy()
        >>> c.read_string_or_raw_until('::', consume_stop=False), c.n_consumed
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

        Until EOF.
        >>> l = Lexer("  'string'  ")
        >>> l.read_string_or_raw_until(EOI), l.n_consumed
        (('string', False), 12)
        >>> l = Lexer("  'raw  ")
        >>> l.read_string_or_raw_until(EOI), l.n_consumed
        (("'raw", True), 8)

        With unwanted data.
        >>> l = Lexer("  'string' unwanted :: next")
        >>> l.read_string_or_raw_until("::")
        Traceback (most recent call last):
        exceptions.ParseError: Unexpected data found between string and '::': 'unwanted'.

        >>> l = Lexer(" unwanted 'string'")
        >>> l.read_string_or_raw_until(EOI)
        Traceback (most recent call last):
        exceptions.ParseError: Unexpected data found before string: 'unwanted'.

        This triggers anytime the remaining raw data would partially parse as a string.
        >>> l = Lexer(" unwanted '''string \'''\"")
        >>> l.read_string_or_raw_until(EOI)
        Traceback (most recent call last):
        exceptions.ParseError: Unexpected data found before string: 'unwanted'.

        >>> l = Lexer("  'string''again' :: next")
        >>> l.read_string_or_raw_until('::')
        Traceback (most recent call last):
        exceptions.ParseError: Unexpected data found between string and '::': "'again'".

        >>> l = Lexer("  'string' 'more")
        >>> l.read_string_or_raw_until(EOI) # doctest: +NORMALIZE_WHITESPACE
        Traceback (most recent call last):
        exceptions.ParseError: Unexpected data found
                               between string and end of input: "'more".

        Overflowing stop marks with unclosed strings.
        >>> l = Lexer(" 'unclosed string :: ne'xt")
        >>> l.read_string_or_raw_until('::'), l.n_consumed
        (None, 0)

        Use guards to not overflow with raw reads.
        >>> l = Lexer(" '''multiline string\n without a need for a guard''' \n :: next")
        >>> l.read_string_or_raw_until('::'), l.n_consumed
        (('multiline string\n without a need for a guard', False), 56)

        >>> l = Lexer(" multiline raw read\n not matching because of guards \n :: next")
        >>> l.read_string_or_raw_until('::'), l.n_consumed
        (None, 0)
        >>> l = Lexer(" override guards \n to make this read \n :: next")
        >>> l.read_string_or_raw_until('::', raw_guards=[]), l.n_consumed
        (('override guards \n to make this read', True), 41)
        """
        if (r := self.read_string_or_raw_until_either([stop], *args, **kwargs)) is None:
            return None
        return r[1], r[2]

    def read_string_or_raw_until_either(
        self, stops, raw_guards=["\n"], consume_stop=True
    ) -> ("stop", str, bool) or None:
        """Same that read_string_or_raw_until,
        but defer to `read_until_either` instead of `read_until`.
        >>> l = Lexer("  'string' :: next")
        >>> l.read_string_or_raw_until_either(['--', 'nosuchstop']), l.n_consumed
        (None, 0)
        >>> l.read_string_or_raw_until_either(['::', EOI]), l.n_consumed
        (('::', 'string', False), 13)

        >>> l.read_string_or_raw_until_either(['::', EOI]), l.n_consumed
        ((EOI, 'next', True), 18)

        >>> l.read_string_or_raw_until_either(['::', '--']), l.n_consumed # Nothing left.
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
            return stop, read, False
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
        return stop, read.strip(), True

    def read_successive_strings(self, until=["#", EOI]):
        """Read an alternated sequence of (stripped) raw reads and/or quoted strings.
        Python's triple quotes are ambiguous in this context are are pretty much
        guaranteed *not* to work fine.

        >>> l = Lexer('''  a "b" this-isn't-one "this is" last ''')
        >>> l.read_successive_strings()
        ['a', 'b', "this-isn't-one", 'this is', 'last']
        >>> # Only one ---v--- char changed.
        >>> l = Lexer(''' "a "b" this-isn't-one "this is" last ''')
        >>> l.read_successive_strings()
        ['a ', 'b', " this-isn't-one ", 'this is" last']
        >>> # Only another char changed -------------v
        >>> l = Lexer('''  a "b" this-isn't-one "this'is" last ''')
        >>> l.read_successive_strings()
        ['a', 'b', 'this-isn', 't-one "this', 'is" last']
        """
        out = False
        stops = ['"', "'"] + until
        results = []
        while True:  # Once for every name.
            raw = None
            while (string := self.read_python_string()) is None:
                if raw is None:
                    raw = ""
                elif self.input:
                    raw += s
                    assert self.match(s)
                s, n = self.read_until_either(stops, False)
                raw += n
                if s in until:
                    out = True
                    break
            if raw is not None:
                raw = raw.strip()
            if raw:
                results.append(raw)
            if string is not None:
                results.append(string)
            if out:
                break
        return results
