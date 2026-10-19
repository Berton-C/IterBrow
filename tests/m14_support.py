"""Shared helpers for the Milestone 14 (the vault and the foundry loop) tests.
Spec: docs/milestones/M14_vault_and_foundry_loop.md.

Not a test module. `pending(item)` = unittest.expectedFailure until the item is implemented (remove the
decorator to activate the test). `M14_IMPLEMENTED` is keyed on iter/iterbrow_runtime/vault.py (A1).

A vault for tests is a throwaway folder beside a throwaway ITER_DIR (`vault_root`): the ITER_DIR's
`.runtime/settings.json` names it, exactly as the person's choice does on the Mac, so every tool and the
catalog find it the way they will in IterBrow. Nothing touches the checkout.
"""
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import REPO, ITER_SRC, NODE, node  # noqa: E402,F401
from m12_support import m12_root, run_tool, tool_text, agents_md, injected_agents_md, main_js  # noqa: E402,F401
from m13_support import fake_bridge, bridge_call, BRIDGE  # noqa: E402,F401

RUNTIME = ITER_SRC / "iterbrow_runtime"
M14_IMPLEMENTED = (RUNTIME / "vault.py").exists()
NEW_TOOLS = ["new_app", "app_rollback", "github"]
EXAMPLES = ("mapstation", "nodequest")
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "m14"


def pending(item):
    assert item.startswith("M14-"), item
    return unittest.expectedFailure


def require_m14():
    if not M14_IMPLEMENTED:
        raise AssertionError("Milestone 14 not implemented: iter/iterbrow_runtime/vault.py is missing")


class VaultRoot:
    """A throwaway ITER_DIR (m12_root) plus a vault folder named in its .runtime/settings.json."""

    def __init__(self, name, with_vault=True, with_main_js=False):
        self.iter = m12_root(name, with_main_js=with_main_js)
        self.root = self.iter.root
        self.vault = self.root.parent / "vault"
        if with_vault:
            self.vault.mkdir()
            self.set_vault(self.vault)

    def set_vault(self, path):
        settings_path = self.root / ".runtime" / "settings.json"
        settings_path.parent.mkdir(exist_ok=True)
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            settings = {}
        if path is None:
            settings.pop("vault", None)
        else:
            settings["vault"] = str(path)
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

    def app(self, app_id, html="<!doctype html><title>%s</title><body data-iter-ready='true'><h1 id='title'>%s</h1>",
            probe=None, brief=None):
        """A vault app with an index.html (and probe.json / brief.json when given); returns its folder."""
        folder = self.vault / app_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(html % (app_id, app_id) if "%s" in html else html, encoding="utf-8")
        if probe is not None:
            (folder / "probe.json").write_text(json.dumps(probe), encoding="utf-8")
        if brief is not None:
            (folder / "brief.json").write_text(json.dumps(brief), encoding="utf-8")
        return folder

    def snapshots(self, app_id):
        """The log entries for an app, oldest first ([] when none)."""
        log = self.vault / ".iter" / "snapshots" / app_id / "log.jsonl"
        if not log.is_file():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def tool(self, name, **kwargs):
        return run_tool(self.iter, name, **kwargs)

    def text(self, name, **kwargs):
        return tool_text(self.iter, name, **kwargs)

    def close(self):
        self.iter.close()
        shutil.rmtree(self.vault, ignore_errors=True)


def vault_root(name, **kwargs):
    if not M14_IMPLEMENTED:
        require_m14()
    return VaultRoot(name, **kwargs)


def vault_module():
    """iterbrow_runtime.vault imported from the checkout (pure functions take explicit roots)."""
    require_m14()
    if str(ITER_SRC) not in sys.path:
        sys.path.insert(0, str(ITER_SRC))
    import importlib
    return importlib.import_module("iterbrow_runtime.vault")


def transformation(name):
    """Import iter/transformations/<name>.py as a module (its pure functions)."""
    import importlib.util
    path = ITER_SRC / "transformations" / (name + ".py")
    if not path.exists():
        raise AssertionError("missing transformation %s" % path)
    spec = importlib.util.spec_from_file_location("m14_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tool_module(name):
    """Import iter/tools/<name>.py for its pure helpers (parsers, url builders)."""
    import importlib.util
    path = ITER_SRC / "tools" / (name + ".py")
    if not path.exists():
        raise AssertionError("missing tool %s" % path)
    if str(ITER_SRC) not in sys.path:
        sys.path.insert(0, str(ITER_SRC))
    spec = importlib.util.spec_from_file_location("m14_tool_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tool_source(name):
    return (ITER_SRC / "tools" / (name + ".py")).read_text(encoding="utf-8")


def runtime_source(name):
    return (RUNTIME / (name + ".py")).read_text(encoding="utf-8")


def assistant(content="", calls=()):
    """A fake assistant message with tool calls [(id, name, arguments-dict)]."""
    message = {"role": "assistant", "content": content, "tool_calls": []}
    for call_id, name, arguments in calls:
        message["tool_calls"].append({"id": call_id, "type": "function",
                                      "function": {"name": name, "arguments": json.dumps(arguments)}})
    return message


def tool_result(call_id, text):
    return {"role": "tool", "tool_call_id": call_id, "content": text}


def user(text):
    return {"role": "user", "content": text}


def system(text="You are Iter."):
    return {"role": "system", "content": text}


def menu_template(catalog, state):
    """bridge/vault_menu.js appsMenuTemplate(catalog, state, handlers) with recording handlers, run in node.

    Returns the template with functions replaced by the handler name they call ("open:todo", "choose", ...)."""
    code, out, err = node("""
const { appsMenuTemplate } = require(%s);
const calls = [];
const handlers = { open: (id) => calls.push('open:' + id), choose: () => calls.push('choose'),
  reveal: () => calls.push('reveal'), switchTo: (p) => calls.push('switch:' + p), undo: (id) => calls.push('undo:' + id) };
const strip = (items) => items.map((item) => {
  const copy = { ...item };
  if (typeof copy.click === 'function') { calls.length = 0; copy.click(); copy.click = calls[0] || 'noop'; }
  if (Array.isArray(copy.submenu)) copy.submenu = strip(copy.submenu);
  return copy;
});
process.stdout.write(JSON.stringify(strip(appsMenuTemplate(%s, %s, handlers))));
""" % (json.dumps(str(BRIDGE / "vault_menu.js")), json.dumps(catalog), json.dumps(state)))
    assert code == 0, err
    return json.loads(out.strip().splitlines()[-1])
