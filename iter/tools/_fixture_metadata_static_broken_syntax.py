# Synthetic fixture: deliberately invalid syntax, simulating a half-written
# file caught mid-save. Static parser must raise StaticParseError (via
# SyntaxError) here, same as the real subprocess path would fail too.
DESCRIPTION = "this file is broken"

def run(a
    return a
