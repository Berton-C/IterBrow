# Synthetic fixture: DESCRIPTION built from an f-string (not a plain literal).
# Static parser must raise StaticParseError here -- this is NOT a real tool,
# it exists only to prove the fallback path triggers correctly.
_name = "world"
DESCRIPTION = f"hello {_name}"

def run(a):
    return a
