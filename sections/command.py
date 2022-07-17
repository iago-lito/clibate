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

from reader import Reader, LinesAutomaton
from test_runner import RunnerWrapperActor


Command = RunnerWrapperActor("update_command", "Command")


class CommandReader(Reader):

    keyword = "command"

    def section_match(self, lexer):
        self.introduce(lexer)
        colon = self.check_colon_type()
        cx = self.keyword_context
        if colon == "::":
            cmd = self.read_heredoc_like("command")
            return Command(cx, cmd)
        return CommandAutomaton(cx)


class CommandAutomaton(LinesAutomaton):
    def __init__(self, context):
        self.context = context
        self.lines = []  # One entry per input line.

    def feed(self, lex):
        # Ignore empty lines and plain comment lines,
        # but keep the rest verbatim so eg. `echo 'ah'` needs no quoting.
        if lex.find("#"):
            return
        self.lines.append(lex.consume().strip())

    def terminate(self):
        return Command(self.context, " ".join(self.lines))
