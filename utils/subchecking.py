"""Both 'Success' and 'Error' sections check output as a substring irrespective of
whitespace. Factorize this common logic here.
"""

from checker import Checker


def substring_in_normalized_whitespace(haystack, needle):
    h, n = (" ".join(s.split()) for s in (haystack, needle))
    return (n in h), n


class StdoutSubChecker(Checker):

    expecting_stdout = True

    def __init__(self, needle):
        self.needle = needle

    def check(self, _, stdout, __):
        stdout = stdout.decode("utf-8")
        isin, normalized = substring_in_normalized_whitespace(stdout, self.needle)
        if isin:
            return None
        if not stdout:
            actual = "found nothing instead."
        else:
            actual = f"found instead:\n{stdout}"
        return f"Stdout: expected to find:\n{normalized}\n{actual}"


class StderrSubChecker(Checker):

    expecting_stderr = True

    def __init__(self, needle):
        self.needle = needle

    def check(self, _, __, stderr):
        stderr = stderr.decode("utf-8")
        isin, normalized = substring_in_normalized_whitespace(stderr, self.needle)
        if isin:
            return None
        if not stderr:
            actual = "found nothing instead."
        else:
            actual = f"found instead:\n{stderr}"
        return f"Stderr: expected to find:\n{normalized}\n{actual}"
