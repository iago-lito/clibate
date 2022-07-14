r"""The Command section specifies the command to be run as a test.

    command: path/to/exec arg1 arg2 | postprocess

Lines in this section are read and passed verbatim to the shell,
as one single command line:

    command: /path/to/exec arg1 arg2
             && run_on_success
             || run_on_failure # This comment is *included*, so the next line is..
             *not* executed because it actually continues the comment above.

Downside: lines are stripped and joined without '\n' characters inside,
and without stripping trailing comments.
Still, lines starting with '#' are excluded as expected:

    command: # This comment is excluded and not sent to the shell.
        exec arg1 arg2 arg3
        # This comment as well, so..
        arg4 'last string-ed arg' # .. this is really part of the command.

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

from actor import Actor
from lexer import Lexer
from reader import Reader, LinesAutomaton


class Command(Actor):
    def __init__(self, command):
        self.command = command

    def execute(self, ts):
        ts.update_command(self.command)


class CommandReader(Reader):

    keyword = "command"

    def match(self, input, _):
        self.introduce(input)
        colon = self.check_colon_type()
        if colon == "::":
            cmd = self.read_heredoc_like("command")
            return self.hard_match(Command(cmd))
        return self.soft_match(CommandAutomaton())


class CommandAutomaton(LinesAutomaton):
    def __init__(self):
        self.lines = []  # One entry per input line.

    def feed(self, line, _):
        # Ignore empty lines and plain comment lines.
        if Lexer(line).find("#"):
            return
        if s := line.strip():
            self.lines.append(s)

    def terminate(self):
        return Command(" ".join(self.lines))
