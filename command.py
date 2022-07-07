from actor import Actor
from lexer import Lexer
from reader import Reader, LinesAutomaton


class Command(Actor):
    """Responsible for updating the command run for the tests."""

    def __init__(self, command):
        self.command = command

    def execute(self, ts):
        ts.update_command(self.command)


class CommandReader(Reader):
    r"""Lines in this section are read and passed verbatim to the shell,
    as one single command line:

        command: exec arg1 arg2 arg3 | exec2 arg5
                 && exec3 > output_file # INCLUDED comment, so..
                 not executed because: .. comment continued here

    Downside: lines are stripped and joined without '\n' characters inside,
    and without stripping trailing comments.
    Still, lines starting with '#' are excluded as expected:

        command: # Excluded comment.
            exec arg1 arg2 arg3
            # Excluded comment, so that..
            arg4 'args 5 and 6' # <-- this is really part of the command.

    To overcome this, use heredoc-like markers instead, which makes the match "hard":

        # Disambiguate this syntax with a double colon '::'
        command:: EOC
            # https://stackoverflow.com/a/1655389/3719101
            read -r -d '' VAR <<'EOF'
            abc'asdf"
            $(dont-execute-this)
            foo"bar"''
            EOF
        EOC # Note that captured text is dedented.

    """

    keyword = "command"

    def match(self, input):
        self.introduce(input)
        colon = self.check_colon_type()
        if colon == "::":
            cmd = self.read_heredoc_like("command")
            return self.hard_match(Command(cmd))
        return self.soft_match(CommandAutomaton())


class CommandAutomaton(LinesAutomaton):
    """Successive lines are appended verbatim to the command,
    ignoring indentation and trailing space.
    """

    def __init__(self):
        self.lines = []  # One entry per input line.

    def feed(self, line):
        # Ignore empty lines and plain comment lines.
        if Lexer(line).find("#"):
            return
        if s := line.strip():
            self.lines.append(s)

    def terminate(self):
        return Command(" ".join(self.lines))
