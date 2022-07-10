"""Common robust parsing functions are shared here.
"""

import ast


def find_python_string(input):
    r"""If the given string starts with a valid python string, parse it and return it
    along with non-consumed input.
    Otherwise return None.
    >>> f = find_python_string
    >>> f("")
    >>> f(" 'test' not-a-string ") # Find first string.
    ('test', ' not-a-string ')
    >>> f(" 'test' # comment") # Don't strip comments.
    ('test', ' # comment')
    >>> f(r' r"raw\'" 54') # Accept any python string syntax.
    ("raw\\'", ' 54')
    >>> f(" '''triple ' quoted''' \"rest") # Accept any python string syntax.
    ("triple ' quoted", ' "rest')
    >>> f(" 74, id ") # Literal is not a string.
    >>> f(" not starting 'with a string'")
    >>> f(" 74 'test'") # starting with a non-string literal
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
    chunks = iter(input.split(quote))
    input = next(chunks) + quote
    while True:
        try:
            input += next(chunks) + quote
        except StopIteration:
            return None
        try:
            string = ast.literal_eval(input)
            break
        except (SyntaxError, ValueError):
            continue
    if type(string) is not str:
        # Parse succeeded but did not result in a python string.
        return None
    return string, quote.join(chunks)
