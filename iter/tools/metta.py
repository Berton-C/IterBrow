import sys
import types
import json as _json

class _MettaUnavailable(RuntimeError):
    pass

_METTA_MSG = ("pymetta engine not installed. MeTTa evaluation unavailable; "
              "reasoning degrades silently. Install: pip install 'pymetta[engine]' "
              "(requires system SWI-Prolog 9.3+).")

try:
    import pymetta  # noqa
except ImportError:
    _m = types.ModuleType("pymetta")
    _m.UNAVAILABLE = True
    def _run_stub(*a, **k):
        return _json.dumps({"error": _METTA_MSG})
    _m.run = _run_stub
    _m.eval = _run_stub
    sys.modules["pymetta"] = _m

"""Evaluate MeTTa with a real, native PeTTa-semantics engine.

This replaces the browser build's WASM SWI-Prolog engine with
MeTTa Kernel (https://github.com/MesTTo/MeTTa-Kernel), a Prolog+C engine
exposed to Python as the `pymetta` package. It follows PeTTa's semantics
(https://github.com/patham9/PeTTa), the same reference implementation the
browser build's WASM engine was compiled from, so behavior should match
closely.

Requirements (not bundled — see README.md "Requirements"):
  - SWI-Prolog 9.3+  (macOS: `brew install swi-prolog`)
  - `pip install 'pymetta[engine]'` inside iter/.venv

Design note: iter.py's invoke_dynamic() spawns a brand-new Python
subprocess for every single tool call (see main iter.py, DYNAMIC_TIMEOUT),
so nothing in this process — including an in-memory MeTTa space — survives
between calls. Each run() therefore starts from a fresh, empty space; it
does not automatically load transformations/.runtime/space.metta (the
app's separately-maintained persistent knowledge file). Pass whatever
facts/equations a call needs as part of `code` itself, or read space.metta
into `code` yourself (e.g. from soul_eval.py) if you want that context.
"""

import os as _os
import sys as _sys
import threading as _threading
import time as _time
import importlib as _importlib
import importlib.util as _importlib_util
import importlib.machinery as _importlib_machinery
from pathlib import Path as _Path

# Default memory ceiling for a single evaluate() call, in megabytes. Enforced by
# a portable RSS-polling watchdog (see _start_memory_watchdog below) rather than
# relying on the OS: setrlimit(RLIMIT_AS) is silently unenforced on macOS (the
# Darwin kernel's mmap-backed allocator ignores it), so it cannot be trusted as
# the real safety mechanism on this app's actual deployment target.
_METTA_MEM_LIMIT_MB = int(_os.environ.get("METTA_MEM_LIMIT_MB", "512"))


def _start_memory_watchdog(limit_mb=_METTA_MEM_LIMIT_MB, poll_interval_s=0.1):
    """Hard-exits this process if its resident memory crosses limit_mb.

    This process is always a fresh, disposable subprocess spawned per-call by
    iter.py's invoke_dynamic(), so a hard os._exit() here is safe -- it never
    touches the main agent loop, and invoke_dynamic already treats "child
    exited without writing a result" as a normal, clean failure to recover
    from (same code path a timeout takes).
    """
    import resource as _resource
    stop_event = _threading.Event()
    limit_bytes = limit_mb * 1024 * 1024

    def _poll():
        while not stop_event.is_set():
            try:
                maxrss = _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss
                # ru_maxrss is KB on Linux, bytes on macOS/BSD.
                rss_bytes = maxrss * 1024 if _sys.platform != "darwin" else maxrss
                if rss_bytes > limit_bytes:
                    _os._exit(137)
            except Exception:
                pass
            stop_event.wait(poll_interval_s)

    thread = _threading.Thread(target=_poll, daemon=True)
    thread.start()
    return stop_event


def _import_pymetta_space():
    # This file is itself named tools/metta.py, and several sibling tools
    # (soul_eval.py, chroma_query.py, preview.py, contradict.py, ...) put
    # THIS DIRECTORY onto sys.path[0] to satisfy their own local imports --
    # soul_eval.py in particular does `import metta as _metta_module`
    # expecting to reach *this file*. That means a plain `from metta import
    # space` here is ambiguous: sys.path search order could resolve "metta"
    # to this very file instead of the real pip-installed pymetta package,
    # causing a circular self-import.
    #
    # To keep both directions working -- other tools' bare `import metta`
    # must still reach this wrapper, AND this wrapper must still reach the
    # real engine -- load the real pymetta package by hand under a private
    # name, searching every sys.path entry except this file's own directory.
    # This never touches sys.modules["metta"], so it can't shadow or be
    # shadowed by whatever else in this process means "metta".
    this_dir = str(_Path(__file__).resolve().parent)
    search_path = [p for p in _sys.path if p and str(_Path(p).resolve()) != this_dir]
    spec = _importlib_machinery.PathFinder.find_spec("metta", path=search_path)
    if spec is None:
        # Fail-open: return a stub space instead of raising, so callers
        # (transformations, soul_eval, iter.py tool calls) degrade silently
        # rather than erroring the whole cycle.
        #
        # BUGFIX (found by log inspection): __call__ used to `return []`
        # instead of `return self`. Callers do `m = _space(); m.run(code)` --
        # with the old code that made `m` a plain empty list, and
        # `[].run(...)` raised AttributeError every single call instead of
        # degrading silently as intended. That in turn made every live-engine
        # validation attempt in nace_courier.py "fail" with a garbled
        # "MeTTa unavailable: AttributeError: 'list' object has no attribute
        # 'run'" message, logged on every cycle forever (the circuit breaker
        # never tripped because tools/metta.py's run() swallowed the
        # exception and returned an '(apparently successful) string, so
        # run_query() never saw ok=False). Returning self here makes __call__
        # actually hand back an object with a working .run(), so the stub
        # degrades the way the comment above always said it should.
        class _StubSpace:
            def __call__(self, *a, **k):
                return self
            def run(self, code, *a, **k):
                return []
            def add_atom(self, *a, **k):
                return None
        return _StubSpace()
    private_name = "_iter_pymetta_engine"
    spec.name = private_name
    if spec.loader is not None:
        spec.loader.name = private_name
    module = _importlib_util.module_from_spec(spec)
    # The package's own internal relative imports (e.g. `from ._atoms_core
    # import X`) need to find their parent under this private name while
    # they run, so it has to be registered during exec_module(). Left in
    # place afterward too, in case anything inside lazily re-resolves itself
    # by module name later -- it's a private key nothing else contends for.
    _sys.modules[private_name] = module
    spec.loader.exec_module(module)
    return module.space


# ENGINE_AVAILABLE lets callers (see tools/_metta_substrate.py's run_query())
# check cheaply, WITHOUT calling run(), whether this is the real pymetta
# engine or the fail-open stub. Callers that hammer this every cycle (the
# NACE courier's live-engine validation pass, the dispatch gate) use this to
# short-circuit straight to a clean, stable "ok": False instead of running
# the stub, mis-parsing its placeholder output, and logging a fresh garbled
# "unparseable engine result" entry every single cycle forever.
ENGINE_AVAILABLE = True

_space = _import_pymetta_space()
if type(_space).__name__ == "_StubSpace":
    ENGINE_AVAILABLE = False

DESCRIPTION = (
    "Evaluate MeTTa with a native PeTTa-semantics engine (MeTTa Kernel, "
    "github.com/MesTTo/MeTTa-Kernel, running on SWI-Prolog). A single bare "
    "S-expression is treated as runnable; for example (+ 1 1) returns 2. "
    "Multi-line programs keep their own syntax unchanged, including any "
    "'!' markers that request an answer."
)


def _unavailable_msg():
    # FIX (2026-09-17 audit): this used bare json.dumps() but the module only
    # imports json as _json -- calling this raised NameError instead of
    # returning the intended message. Dead code today (no caller found in a
    # full-codebase grep), fixed so it is safe the moment something calls it.
    return _json.dumps({"error": "pymetta engine not installed — MeTTa reasoning degraded to silent-fail (by design). Install: pip install 'pymetta[engine]' + SWI-Prolog 9.3+."})

def run(code):
    code = str(code).strip()
    if not code:
        raise ValueError("empty MeTTa code")

    # Tool convenience: a single bare expression is evaluated as a runnable.
    # Full/multiline MeTTa programs retain their syntax unchanged.
    if "\n" not in code and code.startswith("(") and code.endswith(")"):
        code = "!" + code

    try:
        stop_watchdog = _start_memory_watchdog()
        try:
            m = _space()
            try:
                result = m.run(code)
            except Exception as e:
                raise RuntimeError(f"{type(e).__name__}: {e}")
        finally:
            stop_watchdog.set()
        return str(result)
    except Exception as e:
        return _json.dumps({"error": f"MeTTa unavailable: {e}",
                            "hint": "pip install 'pymetta[engine]' + SWI-Prolog 9.3+"})
