"""Internal shared helpers for the MeTTa reasoning-substrate work.

NOT an LLM-facing tool (underscore-prefixed, like _browser_bridge.py and
friends -- iter.py's load_tools() skips these when building the tool list
the LLM sees, but invoke_dynamic() can still call into them directly by
path, which is how transformations/metta_reasoning.py and tools/_metta_gate.py
use this module).

Provides, for anything that wants to reason over the NACE substrate:
  - a portable memory watchdog (see note on macOS below)
  - a legacy projection loader used only by explicit offline compatibility
  - run_query(): evaluates extra facts + a query against the source seeds and
    runtime atoms already owned by the authoritative AtomSpace, returning the
    exact commit identity with the answer.

SAFETY DESIGN NOTES
--------------------
1. Wall-clock: every caller of this module (a transformation's transform(),
   or tools/_metta_gate.py's run()) is itself invoked by iter.py's
   invoke_dynamic(), which already runs it in its own subprocess and hard-
   kills the whole process group after DYNAMIC_TIMEOUT seconds
   (os.killpg(..., SIGKILL)). That backstop is free and needs no code here.

2. Memory: setrlimit(RLIMIT_AS)/RLIMIT_DATA) is well-documented as silently
   unenforced on macOS -- the Darwin kernel's mmap-backed allocator does not
   honor it (processes can exceed the "limit" without any signal). Since
   macOS is this app's actual deployment target, we do NOT rely on it. We
   still attempt it as a free extra layer where the OS *does* honor it
   (mainly Linux), but the real cross-platform protection is a background
   thread that polls this process's own RSS via resource.getrusage (which
   *is* accurate on macOS, unlike setrlimit) and calls os._exit() the moment
   it crosses the ceiling. This is safe because the process running this
   code is always a disposable, single-purpose subprocess.
"""

import os
import sys
import json
import time
import threading

_MAX_SUBSTRATE_CHARS = 200_000  # guard against a corrupted/huge belief file
_BREAKER_PATH_DEFAULT = "memory/.metta_circuit_breaker.json"
_BREAKER_MAX_CONSECUTIVE_FAILURES = 3
_BREAKER_COOLDOWN_S = 300


def _self_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _import_metta_wrapper():
    """Reach tools/metta.py, the authoritative AtomSpace query client.

    We need our own directory on sys.path so a plain `import metta` resolves
    to the tool rather than an unrelated installed module.
    """
    d = _self_dir()
    if d not in sys.path:
        sys.path.insert(0, d)
    import metta as _metta_module
    return _metta_module


def try_setrlimit_as(limit_mb):
    """Best-effort. Known to be a no-op on macOS -- see module docstring."""
    try:
        import resource
        limit_bytes = limit_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
        return True
    except Exception:
        return False


def start_memory_watchdog(limit_mb, poll_interval_s=0.1):
    """Returns a threading.Event; call .set() on it to stop polling cleanly
    once the guarded work is done."""
    import resource
    stop_event = threading.Event()
    limit_bytes = limit_mb * 1024 * 1024

    def _poll():
        while not stop_event.is_set():
            try:
                maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                rss_bytes = maxrss * 1024 if sys.platform != "darwin" else maxrss
                if rss_bytes > limit_bytes:
                    os._exit(137)
            except Exception:
                pass
            stop_event.wait(poll_interval_s)

    threading.Thread(target=_poll, daemon=True).start()
    return stop_event


def _load_breaker(path=_BREAKER_PATH_DEFAULT):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_breaker(state, path=_BREAKER_PATH_DEFAULT):
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception:
        pass


def breaker_should_skip(key, path=_BREAKER_PATH_DEFAULT):
    """True if `key`'s subsystem has failed too many times in a row recently
    and should skip live MeTTa reasoning this cycle (graceful degrade,
    self-protecting against a subsystem that keeps erroring/timing out)."""
    state = _load_breaker(path)
    entry = state.get(key, {})
    fails = entry.get("consecutive_failures", 0)
    tripped_at = entry.get("tripped_at", 0)
    if fails >= _BREAKER_MAX_CONSECUTIVE_FAILURES:
        if time.time() - tripped_at < _BREAKER_COOLDOWN_S:
            return True
    return False


def breaker_record_result(key, ok, path=_BREAKER_PATH_DEFAULT):
    state = _load_breaker(path)
    entry = state.get(key, {"consecutive_failures": 0, "tripped_at": 0})
    if ok:
        entry["consecutive_failures"] = 0
        entry["tripped_at"] = 0
    else:
        entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
        if entry["consecutive_failures"] >= _BREAKER_MAX_CONSECUTIVE_FAILURES:
            entry["tripped_at"] = time.time()
    state[key] = entry
    _save_breaker(state, path)


def load_substrate_and_beliefs(root="."):
    """Static cognitive-operation definitions + live efficacy/calibration
    state, concatenated for an isolated compatibility query. It does not load
    display projections such as space.metta; callers that need extra facts
    must pass them explicitly."""
    parts = []
    for fname in ("nace_substrate.metta", "nace_beliefs.metta"):
        path = os.path.join(root, fname)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            if len(content) > _MAX_SUBSTRATE_CHARS:
                content = content[:_MAX_SUBSTRATE_CHARS]
            parts.append(content)
        except Exception:
            pass
    return "\n\n".join(parts)


def run_query(query_code, extra_facts="", mem_limit_mb=512, root=".",
              include_legacy_projection=False, view="full"):
    """Evaluate `query_code` against one authoritative cognitive commit.

    Source seeds (NACE/KB/lifecycle) and durable belief atoms are reconstructed
    by the service. Re-reading ``nace_beliefs.metta`` here would make a legacy
    projection a competing authority, so it is available only through the
    explicit offline-compatibility flag.

    Returns {"ok": True, "result": str, "epoch": ..., "commit": ...} on success, or
            {"ok": False, "error": str} on any failure -- callers should
    always treat "ok": False as "reasoning substrate unavailable this cycle"
    and apply their declared policy rather than claiming a KB verdict.
    """
    try_setrlimit_as(mem_limit_mb)
    stop_event = start_memory_watchdog(mem_limit_mb)
    try:
        try:
            metta = _import_metta_wrapper()
        except Exception as e:
            return {"ok": False, "error": f"engine unavailable: {type(e).__name__}: {e}"}
        # Detect an unavailable authoritative service before submitting the
        # compatibility query. This gives circuit-breaker callers one stable,
        # honest failure instead of treating placeholder output as reasoning.
        if not getattr(metta, "ENGINE_AVAILABLE", True):
            return {"ok": False, "error": "authoritative Hyperon AtomSpace service is unavailable"}
        base = load_substrate_and_beliefs(root) if include_legacy_projection else ""
        code = "\n\n".join(
            part for part in (base, extra_facts or "", query_code) if part.strip()
        )
        try:
            # This helper's internal facts/expectations are snapshot reads.
            # Arbitrary tools/metta queries remain uncached by default.
            result = metta.query(code, cacheable=not include_legacy_projection, view=view)
            return {
                "ok": True,
                "result": str(result["result"]),
                "epoch": result.get("epoch"),
                "commit": result.get("commit"),
                "state_hash": result.get("state_hash"),
                "authority": "atomspace",
            }
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        stop_event.set()
