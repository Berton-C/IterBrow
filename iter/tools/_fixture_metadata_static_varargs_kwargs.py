# Synthetic fixture: run() uses *args, keyword-only, and **kwargs -- exercises
# the two real files in this codebase (self_improve.py / _self_improve.py)
# that use **kwargs, plus categories (vararg, keyword-only) that don't
# currently exist in any real file but must still be handled correctly.
DESCRIPTION = "fixture tool exercising every parameter kind"

def run(a, *b, c=1, **d):
    return a
