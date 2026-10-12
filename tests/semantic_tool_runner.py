"""Run one tool the way iter.py's dynamic worker does and print a JSON outcome.

usage: semantic_tool_runner.py TOOL_PATH KWARGS_JSON

Test hooks (environment):
  CRASH_AFTER_SAVE=1   die (exit 137) right after the index save, before the
                       pending entry is cleared -- a worker SIGKILLed at 75s.
  NO_REPLY_AFTER_SEND=1  make the AtomSpace call send its request and then
                       report a lost reply (uncertain outcome) without waiting.
  CRASH_BEFORE_SEND=1  die (exit 137) when the transaction is about to be sent:
                       the pending entry exists, nothing was committed.
  FAIL_SAVE=1          the index save raises (disk full / killed after commit):
                       the authority committed, the index did not advance.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

tool_path = Path(sys.argv[1]).resolve()
kwargs = json.loads(sys.argv[2])
component_dir = str(tool_path.parent)
if component_dir not in sys.path:
    sys.path.insert(0, component_dir)

petta = None


def _petta():
    return sys.modules.get("_petta_db")


try:
    hooks = ("CRASH_AFTER_SAVE", "NO_REPLY_AFTER_SEND", "CRASH_BEFORE_SEND", "FAIL_SAVE")
    if any(os.environ.get(hook) == "1" for hook in hooks):
        import _petta_db as petta  # noqa: F811
        if os.environ.get("CRASH_AFTER_SAVE") == "1":
            original_save = petta._save

            def crash_after_save(db, *args, **kw):
                original_save(db, *args, **kw)
                os._exit(137)
            petta._save = crash_after_save
        if os.environ.get("FAIL_SAVE") == "1":
            def failing_save(db, *args, **kw):
                raise OSError(28, "No space left on device (test)")
            petta._save = failing_save
        from iterbrow_runtime import cognitive_events
        original_call = cognitive_events._call_atomspace

        def hooked_call(method, timeout=30, **params):
            if method == "transact" and os.environ.get("CRASH_BEFORE_SEND") == "1":
                os._exit(137)
            if method == "transact" and os.environ.get("NO_REPLY_AFTER_SEND") == "1":
                original_call(method, timeout=timeout, **params)
                raise ConnectionError("AtomSpace closed without a full response")
            return original_call(method, timeout=timeout, **params)
        cognitive_events._call_atomspace = hooked_call
        petta._call_atomspace = hooked_call
    spec = importlib.util.spec_from_file_location("_dynamic_" + tool_path.stem, tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run(**kwargs)
    loaded = _petta()
    print(json.dumps({"ok": True, "result": str(result),
                      "petta_file": getattr(loaded, "__file__", None)}))
except BaseException as error:  # noqa: BLE001 - report everything like dynamic_worker
    loaded = _petta()
    print(json.dumps({"ok": False, "error": "%s: %s" % (type(error).__name__, error),
                      "execution": getattr(error, "execution_outcome", None),
                      "petta_file": getattr(loaded, "__file__", None)}))
