r"""The edit section introduces small changes to files in the test folder,
with a variety of pre-implemented/easy-to-construct edit commands.
Edits are reverted every time a test is run, except if marked with a star '*'.
Thorough documentation in `edit.md` file. Here is just a simple example:

    edit<*> (filename.ext): # Example edit section.

    DIFF a = b + c
       ~ a = b - c

"""

from actor import Actor
from exceptions import ParseError, TestSetError, SourceError, NoSectionMatch
from lexer import Lexer, EOI
from reader import Reader, LinesAutomaton

import re


class Replacer(object):
    """Value associated with one REPLACE instruction in the edit section.
    Modify file content according to the instruction.
    """

    def __init__(self, pattern, replace, all, position):
        self.pattern = re.compile(pattern)
        self.position = position
        self.replace = replace
        self.all = all

    def execute(self, input):
        if not self.pattern.search(input):
            raise TestSetError(
                f"Could not match file with pattern /{self.pattern.pattern}/. "
                f"({self.position})"
            )
        try:
            return self.pattern.sub(self.replace, input, count=int(not self.all))
        except Exception as e:
            raise TestSetError(f"Invalid replace pattern ({self.position}).") from e


class LineProcesser(object):
    """Generic object associated to one line-based edit instruction.
    Determine whether a line matches the instruction.
    Transform the list of lines locally according to the instruction.
    Modify actual provided file content.
    """

    match_patterns = "A|IA|PA|IPA".split("|")
    replace_patterns = "|B|IB|PB|XB|IPB|IXB|PXB|IPXB".split("|")
    replace_patterns += [r.rstrip("B") + "A" for r in replace_patterns if r]
    operations = "inplace above below remove".split()

    def __init__(
        self,
        operation: str,
        # Matching info.
        match_pattern: str,
        P: str or None or re.Pattern,
        A: str,
        T: bool,  # Should we match trailing space?
        all: bool,  # Continue after first match.
        match_position: str,
        # Replacing info (multiple in case of INSERT).
        replace_patterns: [str or None],  # (eg. REMOVE asks for None)
        X_list: [str],
        B_list: [str],
        replace_positions: [str],
    ):

        if match_pattern not in self.match_patterns:
            raise SourceError(f"Invalid match pattern: {repr(match_pattern)}.")
        self.match_pattern = match_pattern
        self.P = P
        self.A = A
        self.T = T

        for rep in replace_patterns:
            if rep is not None and rep not in self.replace_patterns:
                raise SourceError(f"Invalid replace pattern: {repr(rep)}.")
        self.replace_patterns = replace_patterns
        self.X_list = X_list
        self.B_list = B_list

        self.all = all
        if operation not in self.operations:
            raise SourceError(f"Invalid operation: {repr(operation)}.")
        self.operation = operation

        self.match_position = match_position
        self.replace_positions = replace_positions

    def match(self, line):
        """Return None in case of nomatch,
        otherwise, return all necessary information
        for 'self.process()' to correctly work next.
        """
        raise NotImplementedError(f"Missing method 'match' for {type(self).__name__}.")

    def construct(self, match) -> [str]:
        """Build (a) new line(s) from a matched one.
        The received 'match' argument has been produced
        by a consistent 'self.match()' call.
        """
        raise NotImplementedError(
            f"Missing method 'construct' for {type(self).__name__}."
        )

    def edit_lines(self, lines, i_match, constructed_lines) -> int:
        """Process new line(s) in place within their list of lines.
        Return offset to the next line to process,
        so that we don't create loops with insertions.
        """
        if self.operation == "inplace":
            (new_line,) = constructed_lines
            lines[i_match] = new_line
            return 0

        if self.operation == "remove":
            () = constructed_lines
            del lines[i_match]
            return -1

        if self.operation == "below":
            for new_line in reversed(constructed_lines):
                lines.insert(i_match + 1, new_line)
            return len(constructed_lines)

        if self.operation == "above":
            for new_line in reversed(constructed_lines):
                lines.insert(i_match, new_line)
            return len(constructed_lines)

    def execute(self, input):
        """Find matching lines in input, replace them then return modified string."""
        lines = input.split("\n")
        # Scroll all lines to gather matching ones.
        matches = []  # [(i, match_info)]
        for i, line in enumerate(lines):
            if m := self.match(line):
                matches.append((i, m))
                if not self.all:
                    break
        if not matches:
            pref = f" with prefix {self.repr_P}" if self.P is not None else ""
            raise TestSetError(
                f"Could not match line {repr(self.A)}{pref}. ({self.match_position})"
            )
        # Scroll all matches to modify the list of lines.
        offset = 0
        for i_match, m in matches:
            new_lines = self.construct(m)
            delta = self.edit_lines(lines, i_match + offset, new_lines)
            offset += delta
        return "\n".join(lines)

    @property
    def repr_P(self):
        """Override to represent eg. regexes differently."""
        return repr(self.P)


class RegexInstruction(LineProcesser):
    r"""Instructions marked with a '/' mark: user wants explicit manual regexes.

    >>> d = RegexInstruction(
    ...         operation="below",
    ...         match_pattern="PA",
    ...         P=r"(\s*)#\s*",
    ...         A="target",
    ...         T=False,
    ...         all=True,
    ...         match_position='<doctest>',
    ...         replace_patterns=["XB", "XB", None],
    ...         X_list=[r"\1--", r"--\1", None],
    ...         B_list=["transformed", "newtarget", None],
    ...         replace_positions=3*['<doctest>'],
    ...     )

    Nomatch.
    >>> d.match("  target")
    >>> d.match(" # not target")
    >>> d.match(" # target not")

    Match and transform.
    >>> lines = [l:=" #target"]
    >>> (m := d.match(l))
    <re.Match object; span=(0, 2), match=' #'>
    >>> d.edit_lines(lines, 0, d.construct(m))
    2
    >>> lines
    [' #target', ' --transformed', '-- newtarget']

    Thorougher tests in .clib files testing the edit section.
    """

    # Wrap interface to check consistency.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.match_pattern == "PA":
            raise SourceError(
                "Invalid match pattern for /-marked instruction: "
                f"{repr(self.match_pattern)}. Expected 'PA'. ({self.match_position})"
            )
        for rep, pos in zip(self.replace_patterns, self.replace_positions):
            if rep not in (None, "XB", "XA"):
                raise SourceError(
                    "Invalid replace pattern for /-marked instruction: "
                    f"{repr(pat)}. Expected '', 'XA' or 'XB'. ({pos})"
                )
        self.P = re.compile(self.P)

    @property
    def repr_prefix_pattern(self):
        return f"/{self.P.pattern}/"

    def match(self, line):
        P = re.compile(self.P)
        if m := P.match(line):
            header = m.group(0)
            A = line.removeprefix(header)
            if not self.T:
                A = A.rstrip()
            if A == self.A:
                return m
        return None

    def construct(self, match):
        lines = []
        for rep, X, B in zip(self.replace_patterns, self.X_list, self.B_list):
            if rep is None:
                # This is a REMOVE/ instruction.
                continue
            if rep.startswith("X"):
                if X is None:
                    # This is UNPREF/ instruction.
                    try:
                        X = match.group(1)  # Still, first group is kept.
                    except IndexError:
                        X = ""
                else:
                    # This is PREFIX/ instruction.
                    X = match.re.sub(X, match.group(0))
                line = X + (B if rep.endswith("B") else self.A)
            lines.append(line)
        return lines


class AutomaticInstruction(LineProcesser):
    """Instruction not marked with a '/': user relies on clib edit section's language.

    >>> d = AutomaticInstruction(
    ...         operation='above',
    ...         match_pattern="IPA",
    ...         P="# ",
    ...         A="target ",
    ...         T=True,
    ...         all=True,
    ...         match_position="<doctest>",
    ...         replace_patterns=['IXB', 'IPXB'],
    ...         X_list=["##!", "-"],
    ...         B_list=["new", "fresh "],
    ...         replace_positions=2*['<doctest>'],
    ...     )

    Nomatch.
    >>> d.match("  target")
    >>> d.match(" #target")
    >>> d.match(" # target not")
    >>> d.match(" # not target")
    >>> d.match(" # target") # Missing trailing whitespace.

    Match and transform.
    >>> lines = [l:=" # target "]
    >>> (m := d.match(l)) # (return I, P, A)
    (' ', '# ', 'target ')
    >>> d.edit_lines(lines, 0, d.construct(m))
    2
    >>> lines
    [' ##!new', ' # -fresh ', ' # target ']

    Thorougher tests in .clib files testing the edit section.
    """

    def match(self, line):
        if self.match_pattern.startswith("I"):
            PA = line.lstrip()
            I = line.removesuffix(PA)
        else:
            PA = line
            I = ""
        if "P" in self.match_pattern:
            P = self.P if self.P is not None else ""
            if not PA.startswith(P):
                return None
            A = PA.removeprefix(P)
        else:
            P = ""
            A = line
        A_ws = A  # Preserve trailing whitespace in case it's used for replacing.
        if not self.T:
            A = A.rstrip()
        if not A == self.A:
            return None
        return (I, P, A_ws)

    def construct(self, match):
        I, P, A = match
        lines = []
        for rep, X, B in zip(self.replace_patterns, self.X_list, self.B_list):
            if rep is None:
                # For REMOVE instruction.
                continue
            l = locals()
            line = "".join(eval(c, l) for c in list(rep))  # <3 Python.
            lines.append(line)
        return lines


class Edit(Actor):
    """Gather executable instructions together,
    then sequentially run them to modify the file.
    """

    def __init__(self, filename, persistent):
        self.filename = filename
        self.persistent = persistent
        self.substitutions = []

    def execute(self, ts):
        # Backup the file before reading it into memory.
        ts.check_test_file(self.filename)
        if not self.persistent:
            ts.backup_file(self.filename, override=False)
        with open(self.filename, "r") as file:
            content = file.read()
        # Run all substitutions in order to the content.
        for sub in self.substitutions:
            content = sub.execute(content)
        # Write the file to disk again.
        with open(self.filename, "w") as file:
            file.write(content)


class EditReader(Reader):

    keyword = "edit"

    def match(self, input, context):
        """Process input line-by-line with an internal LinesAutomaton,
        but overall result is a hard match.
        In this fashion, unrecognized 'edit' instructions
        are forwarded to the parser for an attempt to be recognized
        by other readers.
        """
        self.introduce(input)
        persistent = self.find("*")
        filename = self.read_tuple(1)
        self.check_colon()
        aut = EditAutomaton(filename, persistent)
        # TODO: this should be made way easier with a proper ParseContext to pass around.
        mock_context = context.copy()
        mock_context.consume(self.lexer.n_consumed)
        while self.lexer.input:
            before_line = self.lexer.copy()
            stop, line = self.lexer.read_until_either(["\n", EOI])
            try:
                aut.feed(line, mock_context)
            except ParseError as e:
                # Fix position before forwarding to the parser.
                e.n_consumed -= stop == "\n"
                raise e from e
            except NoSectionMatch:
                # Not sure this is edit section anymore,
                # backtrack and leave the rest to the parser.
                self.lexer.become(before_line)
                break
            mock_context.consume(len(line) + (stop == "\n"))
        parsed = aut.terminate()
        return self.hard_match(parsed)


class EditAutomaton(LinesAutomaton):
    """Edit automaton compiles regexes on the fly
    so that errors in their syntax are caught the earliest possible.
    """

    instructions = ("DIFF", "INSERT", "REMOVE", "PREFIX", "UNPREF", "REPLACE")

    def __init__(self, *args):
        """Use the state to not forget whether we're reading
        eg. a DIFF line or a REPLACE line.
        """
        self.actor = Edit(*args)
        # Current instruction is considered the automaton main state.
        self.state = None
        # Use position to report parsing errors.
        self.state_position = None
        # More refined state information (eg. DIFF prefixes, INSERT above or below)
        # are stored in this scratchspace aggregate.
        self.data = lambda _: None  # (use like a dict but with `.` access, not `[""]`)

    def reset(self):
        """Clear state and expect a new instruction."""
        self.state = None
        self.data.__dict__.clear()

    integer = re.compile(r"(\d+)")

    @classmethod
    def parse_condensed_prefix(cls, input):
        r"""Transform special prefix notation with digits inside into a literal prefix.
        >>> p = EditAutomaton.parse_condensed_prefix
        >>> p('1t2s')
        '\t  '
        >>> p('#2m14s')
        '#mm              '
        >>> p('4')
        '    '
        >>> p('long4sspaced4sphrase')
        'long    spaced    phrase'
        >>> p('nodigits')
        'nodigits'
        """
        if not cls.integer.search(input):
            return input
        input = iter(cls.integer.split(input))
        result = next(input)
        n = int(next(input))
        while True:
            chunk = next(input)
            if not chunk:
                result += n * " "
                break
            if len(c := chunk) == 1:
                rest = ""
            else:
                c = chunk[0]
                rest = chunk[1:]
            if c == "t":
                result += n * "\t" + rest
            elif c == "s":
                result += n * " " + rest
            else:
                result += n * c + rest
            try:
                n = int(next(input))
            except StopIteration:
                break
        return result

    def terminate_instruction(self):
        """All necessary information for the recording
        of a new instruction has been found, and correctly set
        into `self.data` as hidden arguments.
        Construct the instruction then reset.
        """
        d = self.data
        dd = d.__dict__
        P, X, A, B, T = (dd[c] if c in dd else None for c in "PXABT")
        # Upgrade simple replacement patterns to a list
        # to conform to the general case (because INSERT has several).
        if type(X) is not list:
            X = [X]
        if type(B) is not list:
            B = [B]
        if hasattr(d, "replace_pattern"):
            if hasattr(d, "replace_patterns"):
                raise SourceError(f"Confusion with this data names?")
            d.replace_patterns = [d.replace_pattern]
        if hasattr(d, "replace_position"):
            if hasattr(d, "replace_positions"):
                raise SourceError(f"Confusion with this data names?")
            d.replace_positions = [d.replace_position]
        # fmt: off
        instruction = d.InstructionType(
                d.operation,
                d.match_pattern, P, A, T, d.all, d.match_position,
                d.replace_patterns, X, B, d.replace_positions,
                )
        # fmt: on
        self.actor.substitutions.append(instruction)
        self.reset()

    def new_paired_lines_instruction(self, operation):
        """All necessary information for DIFF or INSERT has been found.
        Now interpret and collect.
        """
        d = self.data

        d.operation = operation

        if d.regexes:
            d.replace_patterns = len(d.X) * ["XB"]

        else:
            # Here is the goofy logic to make the stars not often needed.
            P = d.P
            S = "I" if (P is not None) == d.match_star else ""
            d.match_pattern = S + "PA"

            d.replace_patterns = []
            for X, replace_star, pos_replace_star in zip(
                d.X, d.replace_stars, d.pos_replace_stars
            ):

                if replace_star == "**" and (P is None or not d.match_star):
                    raise ParseError(
                        "Double replace star mark '**' is meaningless "
                        "without matching both variable indent (I) and a fixed prefix (P)."
                        f" ({pos_replace_star})"
                    )
                if P is None and d.match_star and replace_star:
                    d.lex.error(
                        "Replace star mark '*' is redundant "
                        "when matching with no indent (I) and no prefix (P)."
                        f" ({pos_replace_star})"
                    )
                # Now screen all valid cases.
                if P is None and not d.match_star:
                    K = "" if replace_star else "I"
                elif P is None and d.match_star:
                    K = ""
                elif P is not None and not d.match_star:
                    K = "P" if bool(X) == bool(replace_star) else ""
                elif P is not None and d.match_star:
                    if replace_star == "**":
                        K = ""
                    else:
                        K = "IP" if bool(X) == bool(replace_star) else "I"

                d.replace_patterns.append(K + "XB")

        self.terminate_instruction()

    def new_replace_instruction(self):
        """We have collected all lines in REPLACE subsection,
        now interpret them and construct corresponding instruction.
        """
        d = self.data
        if not d.by:
            d.lex.error(
                "Cannot split REPLACE instruction over multiple lines "
                f"without expliciting a BY section ({d.line_position})."
            )
        instruction = Replacer(
            "".join(pat for pat, _ in d.replace),
            "".join(rep for rep, _ in d.by),
            d.all,
            d.match_position,
        )
        self.actor.substitutions.append(instruction)
        self.reset()

    def feed(self, line, context):
        self.context = context  # To access from other methods.
        data = self.data
        data.lex = lex = Lexer(line)
        data.line_position = context.position
        if lex.find_empty_line():
            return

        if self.state is None:

            # Expect new instruction.
            keyword = None
            for ins in self.instructions:
                if lex.find(ins):
                    keyword = ins
                    break
            if not keyword:
                # That's a nomatch, leave it to the general parser.
                raise NoSectionMatch()
            self.state = keyword
            self.state_position = context.position

            # Single-line instructions look much alike, apart from the leading tuple.
            if keyword in ("PREFIX", "UNPREF", "REMOVE"):

                data.match_position = data.line_position
                data.replace_position = data.line_position

                if keyword == "PREFIX":
                    data.operation = "inplace"

                    # Match prefix (P) is optional, not replace prefix (X).
                    PX = self.read_single_match_line(2)
                    if PX is None:
                        lex.error(
                            "Missing parenthesized prefix pattern(s)"
                            f"for PREFIX instruction.",
                            pos=data.PX_position,
                        )
                    if len(PX) == 1:
                        data.P, data.X = None, PX
                    if len(PX) == 2:
                        data.P, data.X = PX

                    # Construct corresponding patterns.
                    if data.regexes:
                        data.replace_pattern = "XA"
                    else:
                        # Here is the goofy logic to make the stars not often needed.
                        S = "I" if (data.P is not None) == data.match_star else ""
                        data.match_pattern = S + "PA"
                        data.replace_pattern = S + "PXA"

                if keyword == "UNPREF":
                    data.operation = "inplace"

                    # Match prefix (P) is mandatory, and X cannot be specified.
                    PX = self.read_single_match_line(1)
                    if PX is None:
                        lex.error(
                            "Missing parenthesized prefix to remove"
                            f"for UNPREF instruction.",
                            pos=data.PX_position,
                        )
                    (data.P,) = PX
                    data.X = None

                    # Construct corresponding patterns.
                    if data.regexes:
                        data.replace_pattern = "XA"
                    else:
                        # Here is the goofy logic to make the stars not often needed.
                        S = "I" if not data.match_star else ""
                        data.match_pattern = S + "PA"
                        data.replace_pattern = S + "A"

                if keyword == "REMOVE":
                    data.operation = "remove"
                    data.replace_pattern = None

                    # Mach prefix is optional, and X cannot be specified.
                    PX = self.read_single_match_line(1)
                    data.P = None if PX is None else PX[0]
                    data.X = None

                    # Here is the goofy logic to make the stars not often needed.
                    S = "I" if (data.P is not None) == data.match_star else ""
                    data.match_pattern = S + "PA"

                self.terminate_instruction()
                return

            # Paired-line instructions (DIFF/INSERT)are more sophisticated to parse.
            if keyword == "DIFF":
                self.read_slash()
                self.read_paired_match_line()
                return

            # In particular, INSERT instructions need to spawn a sub-automaton
            # to collect all inserted lines.
            if keyword == "INSERT":
                # The exact status of 'below' is indeterminate yet,
                # but it'll soon become a boolean.
                data.below = lex.find_either(["BELOW", "ABOVE"])
                self.read_slash()
                f = lex.find_either(["+", "ALL"])
                if f == "+":
                    # Expect INSERT ABOVE behaviour.
                    if data.below == "BELOW":
                        lex.error(
                            "Unexpected '+' symbol: "
                            "should appear before the lines to insert, "
                            "so not the top line in case of INSERT BELOW."
                        )
                    else:
                        self.read_paired_replace_line()
                    data.below = False
                elif f in ("ALL", None):
                    # Expect INSERT BELOW behaviour.
                    if data.below == "ABOVE":
                        lex.error(
                            "Missing '+' symbol "
                            "to introduce lines to INSERT ABOVE the match line."
                        )
                    else:
                        self.read_paired_match_line()
                    if f == "ALL":
                        # If we have found this before,
                        # then read_paired_match_line() has missed it.
                        data.all = True
                    data.below = True
                return

            # Like INSERT, REPLACE may span over multiple lines.
            if keyword == "REPLACE":
                self.read_match_all()
                # The first replace line parses specially
                # because it may contain two quoted strings instead of one.
                # Attempt to retrieve 'replace' and 'pattern' on this line alone.
                if (pattern := lex.read_python_string()) is not None:
                    if lex.find("BY"):
                        replace = lex.read_string_or_raw_line(
                            expect_data="replace pattern"
                        )
                        found_replace = True
                    else:
                        # No 'BY' keyword on this line, expect it on subsequent lines.
                        lex.check_empty_line()
                        found_replace = False
                else:
                    # Attempt to find them with a raw read instead.
                    splitter = re.compile(r"\bBY\b")  # Robust to eg. 'BYE'.
                    if (r := lex.read_until(splitter)) is not None:
                        pattern, _ = r
                        if not (pattern := pattern.strip()):
                            lex.error(
                                "Found no match pattern before 'BY' keyword.",
                                len(replace) + len("BY"),
                            )
                        replace = lex.read_python_string()
                        if replace is None:
                            if lex.read_until(splitter) is not None:
                                lex.error(
                                    "Ambiguous raw REPLACE line "
                                    "with more than 1 occurence of the 'BY' keyword. "
                                    "Consider quoting match and/or replace pattern."
                                )
                            replace = lex.read_line(expect_data="replace pattern")
                        else:
                            lex.check_empty_line()
                        found_replace = True
                    else:
                        # Could not find the separating keyword, expect it later.
                        pattern = lex.read_line(expect_data="match pattern")
                        found_replace = False

                data.match_position = data.line_position

                if found_replace:
                    # We have everything to not need to get further.
                    instruction = Replacer(
                        pattern, replace, data.all, data.match_position
                    )
                    self.actor.substitutions.append(instruction)
                    self.reset()
                    return

                # All the above is just considered the first replace line
                # in a multiline replace section.
                # Collect all lines in two separate 'REPLACE' and 'BY' sections
                # then only wrap up to interpret them.
                data.by_found = False  # Raise when 'BY' section is found.
                data.replace = [(pattern, data.line_position)]
                data.by = []  # Empty yet.
                return

            raise NotImplementedError(
                f"Missing code to process edit {keyword} instruction."
            )

        if self.state == "DIFF":
            # Expect the second diff line.
            if not lex.find("~"):
                lex.error(
                    "Missing introducing tilde '~' "
                    f"on second diff line. ({context.position})"
                )
            self.read_paired_replace_line()
            self.new_paired_lines_instruction("inplace")
            return

        if self.state == "INSERT":
            if data.below:
                # Expect replace lines.
                if lex.find("+"):
                    self.read_paired_replace_line()
                    return
                # Was there at least one?
                if not hasattr(data, "X"):
                    lex.error(
                        "No found no lines to INSERT BELOW (marked wit a '+' symbol)."
                    )
                # When there are no more, try a different parsing instead.
                self.new_paired_lines_instruction("below")
                return self.feed(line, context)
            else:
                # Expect more replace lines or one terminating match line.
                if lex.find("+"):
                    self.read_paired_replace_line()
                    return
                self.read_paired_match_line()
                # Was there at least one?
                if not hasattr(data, "X"):
                    lex.error(
                        "No found no lines to INSERT ABOVE (marked wit a '+' symbol)."
                    )
                self.new_paired_lines_instruction("above")
                return

        if self.state == "REPLACE":
            f = lex.find_either(["/", "BY"])
            if f is None:
                # Done with this instruction, leave this line to the next sections.
                self.new_replace_instruction()
                raise NoSectionMatch()
            if f == "BY":
                if data.by:
                    line, pos = data.by[0]
                    line = delineate_string(line)
                    lex.error(
                        "Cannot specify more than one BY line. "
                        f"First BY line already found at {pos}: {line}. "
                        f"To continuate BY lines, prefix them with a '/' mark instead."
                    )
                # First BY line found.
                line, _ = lex.read_string_or_raw_line()
                data.by.append((line, data.line_position))
                return
            if f == "/":
                # Keep reading current subsection.
                line, _ = lex.read_string_or_raw_line()
                record = (line, data.line_position)
                if not data.by:
                    data.replace.append(record)
                else:
                    data.by.append(record)
                return

        raise NotImplementedError("")

    def read_slash(self):
        """Parse whether the slash mark '/' is given and remember position."""
        data = self.data
        lex = data.lex
        data.regexes, data.n_slash = lex.find("/"), lex.n_consumed
        if data.regexes:
            data.match_pattern = "PA"
            data.InstructionType = RegexInstruction
        else:
            data.InstructionType = AutomaticInstruction

    def read_match_star(self):
        """Parse whether match line is marked with a star '*'."""
        data = self.data
        lex = data.lex
        data.match_star, data.n_match_star = lex.find("*"), lex.n_consumed

    def read_match_all(self):
        """Parse whether all matching lines are required."""
        data = self.data
        lex = data.lex
        data.all = lex.find("ALL")

    def read_single_match_line(self, max_n_prefixes: int) -> None or (str,):
        """Common parsing for PREFIX/UNPREF/REMOVE instructions.
        Returns a tuple whose length is 1 <= len(tup) <= max_n_prefixes.
        """
        data = self.data
        lex = data.lex
        # Read various options.
        self.read_slash()
        if not data.regexes:
            self.read_match_star()
        self.read_match_all()
        # Find optional prefix(es) patterns.
        lex.lstrip()
        data.PX_position = lex.n_consumed
        try:
            PX = lex.read_tuple(list(range(max_n_prefixes + 1)))
        except ParseError:
            if data.regexes:
                lex.error(
                    "Requested regex prefix with '/' mark "
                    "but no parenthesized '(pattern)' was provided.",
                    pos=data.n_slash,
                )
            PX = None
        if not (data.regexes or PX is None):
            PX = [self.parse_condensed_prefix(pat) for pat in PX]
            if len(PX) == 0:
                PX = ("",)
        # And mandatory line.
        data.A, data.T = self.read_line_body()
        return PX

    def read_paired_match_line(self) -> (str, bool):
        """Common parsing for DIFF/INSERT instructions."""
        data = self.data
        lex = data.lex
        data.match_position = data.line_position
        # Read various options.
        self.read_match_all()
        self.read_match_star()
        # Find optional prefix.
        try:
            P = lex.read_tuple(1)
        except ParseError:
            if data.regexes:
                lex.error(
                    "Requested regex prefix with '/' mark "
                    "but no parenthesized '(pattern)' was provided.",
                    pos=data.n_slash,
                )
            P = None
        if not (data.regexes or P is None):
            P = self.parse_condensed_prefix(P)
        data.P = P
        # And mandatory line.
        data.A, data.T = self.read_line_body()

    def read_paired_replace_line(self) -> (str, bool):
        """Common parsing for DIFF/INSERT instructions."""
        data = self.data
        lex = data.lex
        replace_positions = data.line_position
        replace_stars = lex.find_either(["**", "*", ""])
        pos_replace_stars = self.context.position
        try:
            X = lex.read_tuple([0, 1])
        except ParseError:
            if data.regexes:
                lex.error(
                    "Requested regex prefix with '/' mark "
                    "but no parenthesized '(replacement)' pattern was provided.",
                )
            X = ""
        X = X[0] if X else ""
        if not data.regexes:
            X = self.parse_condensed_prefix(X)
        B, star = self.read_line_body()
        if star:
            lex.error("Unexpected star mark '*' found after replace line body.")

        # Append to lists or create then. (ask forgiveness not permission)
        for varname in (
            "replace_stars",
            "pos_replace_stars",
            "X",
            "B",
            "replace_positions",
        ):
            value = eval(varname)
            try:
                getattr(data, varname).append(value)
            except AttributeError:
                setattr(data, varname, [value])

    def read_line_body(self) -> (str, bool):
        """Line body is either a raw read until EOL or comment sign, or a quoted string.
        When quoted, it may also be suffixed by a star mark '*'
        to request exact tail matching.
        The star mark is implicit if the line is quoted *and* it ends with whitespace.
        """
        lex = self.data.lex
        if (body := lex.read_python_string()) is not None:
            starred = lex.find("*") or body != body.rstrip()
            lex.check_empty_line()
            return body, starred
        body, _ = lex.read_string_or_raw_line()
        return body, False

    def terminate(self):
        if self.state == "DIFF":
            raise ParseError(f"Missing second DIFF line. ({self.state_position})")
        elif self.state == "INSERT":
            if self.data.below:
                # It's okay, just finish up with the last replace line found.
                self.new_paired_lines_instruction("below")
            else:
                raise ParseError(
                    "Missing match line (without '+' symbol) " "after inserted lines."
                )
        elif self.state == "REPLACE":
            # It's okay, we have collected all the lines we needed.
            self.new_replace_instruction()
        elif self.state is not None:
            raise ParseError(
                f"Edit automaton ended in non-terminal state. ({self.state_position})"
            )
        return self.actor
