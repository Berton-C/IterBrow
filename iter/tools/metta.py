"""Evaluate MeTTa against IterBrow's persistent, real hyperon atomspace.

REPLACES the old pymetta/SWI-Prolog design (see git history of this file
for that version). This is now a thin client -- like tools/_browser_bridge.py
is to bridge/browser_bridge_server.js -- talking over a Unix socket to
metta_server.py, a single long-lived process that holds ONE real
hyperon.MeTTa() atomspace for the app's entire session, auto-started by
`npm start` (see main.js's startMettaServer()).

Why this replaced the old design: the old docstring here said it outright --
"iter.py's invoke_dynamic() spawns a brand-new Python subprocess for every
single tool call... so nothing in this process -- including an in-memory
MeTTa space -- survives between calls." A real atomspace only pays for
itself if state actually accumulates across calls. It now does: every call
into run() reaches the SAME space that was seeded at boot with every
*.metta file under iter/ (795+ atoms verified loading cleanly from real
production data on 2026-09-19, hyperon 0.2.10), and any atoms added at
runtime persist there for as long as the server process runs -- i.e. across
every tool call in the session, not just within one.

Public surface is unchanged on purpose, so every existing caller (soul_eval.py,
tools/_metta_substrate.py, tools/_metta_gate.py, etc. -- see full caller list
in this repo's commit history / IterBrow's own docs) keeps working with zero
changes:
    run(code)          -> str            (same signature/return type as before)
    ENGINE_AVAILABLE    -> bool           (True iff the real engine responded)
    DESCRIPTION         -> str
"""
import sys as _sys
from pathlib import Path as _Path

# tools/_metta_bridge.py lives next to this file. Some sibling tools put
# THIS DIRECTORY on sys.path[0] for their own reasons (see _browser_bridge.py
# precedent) -- make sure we can always reach our own sibling regardless.
_this_dir = str(_Path(__file__).resolve().parent)
if _this_dir not in _sys.path:
    _sys.path.insert(0, _this_dir)

from _metta_bridge import call as _bridge_call, is_running as _bridge_is_running

DESCRIPTION = (
    "Evaluate MeTTa against IterBrow's persistent, real hyperon atomspace "
    "(github.com/trueagi-io/hyperon-experimental). The space is seeded at "
    "app startup with every .metta file under iter/, and accumulates new "
    "atoms across the whole running session -- not just within one call. "
    "A single bare S-expression is treated as runnable; for example (+ 1 1) "
    "returns 2. Multi-line programs keep their own syntax unchanged, "
    "including any '!' markers that request an answer."
)


def _check_engine_available():
    if not _bridge_is_running():
        return False
    try:
        status = _bridge_call("status", timeout=5)
        return bool(status and status.get("engine_available"))
    except Exception:
        return False


# ENGINE_AVAILABLE lets callers (see tools/_metta_substrate.py's run_query())
# check cheaply, without calling run(), whether the real persistent engine is
# reachable. Computed once at import time -- same cost/usage pattern the old
# stub-detection flag had. If the server starts later in the same session,
# callers already holding a stale False can re-check by re-importing or by
# calling run() directly (it always talks live to the server regardless of
# this flag).
ENGINE_AVAILABLE = _check_engine_available()


def run(code):
    """Evaluate `code` against the persistent atomspace and return the
    result as a string -- same contract the old per-call pymetta wrapper had,
    so no caller needs to change. Raises/returns errors the same shape as
    before: on failure, returns a JSON string with an "error" key instead of
    throwing, since every existing caller was written to expect that."""
    import json as _json

    try:
        result = _bridge_call("run", timeout=30, code=code)
        return str(result)
    except Exception as e:
        return _json.dumps({
            "error": f"MeTTa unavailable: {e}",
            "hint": "The persistent MeTTa server should auto-start with `npm start`. "
                    "If this error persists, check the Electron app's startup logs.",
        })
