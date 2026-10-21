"""Shared helpers for the Milestone 15 (the build ledger) tests. Spec: docs/milestones/M15_build_ledger.md.

Not a test module. `pending(item)` = unittest.expectedFailure until the item is implemented (remove the
decorator to activate the test). `M15_IMPLEMENTED` is keyed on iter/iterbrow_runtime/build_ledger.py (C1).

MeTTa rules are tested with the real Hyperon through the one-shot query worker (`run_metta`), exactly as the
service evaluates a query: the seed units first, then the atoms, then the `!` lines.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import REPO, ITER_SRC, NODE, node  # noqa: E402,F401
from m12_support import m12_root, run_tool, tool_text, agents_md  # noqa: E402,F401
from m14_support import VaultRoot, assistant, tool_result, user, system, transformation  # noqa: E402,F401
from semantic_memory_support import PYTHON  # noqa: E402

RUNTIME = ITER_SRC / "iterbrow_runtime"
M15_IMPLEMENTED = (RUNTIME / "build_ledger.py").exists()
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "m15"
SEED = ITER_SRC / "seeds" / "build_ledger.metta"


def pending(item):
    assert item.startswith("M15-"), item
    return unittest.expectedFailure


def require_m15():
    if not M15_IMPLEMENTED:
        raise AssertionError("Milestone 15 not implemented: iter/iterbrow_runtime/build_ledger.py is missing")


def hyperon_available():
    try:
        out = subprocess.run([PYTHON, "-c", "import hyperon"], capture_output=True, timeout=60)
        return out.returncode == 0
    except Exception:
        return False


def runtime_module(name):
    """Import iter/iterbrow_runtime/<name>.py (pure functions)."""
    import importlib
    if str(ITER_SRC) not in sys.path:
        sys.path.insert(0, str(ITER_SRC))
    return importlib.import_module("iterbrow_runtime." + name)


def ledger():
    require_m15()
    return runtime_module("build_ledger")


def seed_units():
    """The rule units of seeds/build_ledger.metta, split the way the service splits a seed file."""
    if str(ITER_SRC) not in sys.path:
        sys.path.insert(0, str(ITER_SRC))
    import metta_server
    return list(metta_server._logical_units(SEED.read_text(encoding="utf-8")))


def run_metta(units, atoms, code, timeout=120):
    """str(results) of evaluating `code` over `units` (rules) + `atoms` ({key: source}) in the real
    Hyperon, through iter/metta_query_worker.py as the service does."""
    work = Path(tempfile.mkdtemp(prefix="m15-metta-"))
    payload = {"schema_version": 1, "epoch": 1, "commit": 1, "state_hash": "test", "seed_units": list(units),
               "atoms": dict(atoms), "code": code, "working_dir": str(work / "queries")}
    proc = subprocess.run([PYTHON, str(ITER_SRC / "metta_query_worker.py")], input=json.dumps(payload), text=True,
                          capture_output=True, cwd=str(ITER_SRC), timeout=timeout)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert lines, proc.stderr[-2000:]
    response = json.loads(lines[-1])
    assert response.get("ok"), response.get("error")
    return str(response.get("result", ""))


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def briefs():
    return json.loads((REPO / "scripts" / "foundry_bench" / "briefs.json").read_text(encoding="utf-8"))


def openai_tools(names, description="A tool.", chars=0):
    """Tool dicts the loop hands to transformations ({type: function, function: {name, description, parameters}})."""
    text = description + ("x" * chars)
    return [{"type": "function", "function": {"name": name, "description": text,
                                              "parameters": {"type": "object", "properties": {"arg": {"type": "string"}}, "required": []}}}
            for name in names]


def real_tools():
    """Every real tool as the loop would offer it: name, DESCRIPTION, and a parameter schema from run()'s signature."""
    import importlib.util
    import inspect
    if str(ITER_SRC) not in sys.path:
        sys.path.insert(0, str(ITER_SRC))
    out = []
    for path in sorted((ITER_SRC / "tools").glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location("m15_tool_" + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            params = [p for p in inspect.signature(module.run).parameters.values()
                      if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)]
        except Exception:
            continue
        out.append({"type": "function", "function": {
            "name": path.stem, "description": str(getattr(module, "DESCRIPTION", "")),
            "parameters": {"type": "object", "properties": {p.name: {"type": "string"} for p in params},
                           "required": [p.name for p in params if p.default is inspect.Parameter.empty]}}})
    return out


def run_in_file_page(html, expression, setup_js="0", wait_ms=100):
    """Like m13_support.run_in_page, but the page is a file:// document (as IterBrow's apps are), so it has
    localStorage (an about:blank page from set_content has an opaque origin and none)."""
    from m6_support import run_playwright
    folder = Path(tempfile.mkdtemp(prefix="m15-page-"))
    page = folder / "index.html"
    page.write_text(html, encoding="utf-8")
    script = """
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 900, "height": 600})
    pg.goto(%s); pg.wait_for_timeout(50)
    pg.evaluate(%s); pg.wait_for_timeout(%d)
    print(json.dumps(pg.evaluate(%s))); b.close()
""" % (json.dumps(page.as_uri()), json.dumps(setup_js), wait_ms, json.dumps(expression))
    return json.loads(run_playwright(script).strip().splitlines()[-1])
