"""Shared helpers for the Milestone 12 (the builder's hands) tests. Spec: docs/milestones/M12_builder_hands.md.

Not a test module. `pending(item)` = unittest.expectedFailure until the item is implemented (remove the
decorator to activate the test). `M12_IMPLEMENTED` is keyed on iter/tools/read_file.py. Tool tests run the
tool in a fresh process inside a throwaway ITER_DIR (SemanticRoot, as M6–M10 did), so nothing touches
the checkout.
"""
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import REPO, ITER_SRC, NODE, node  # noqa: E402,F401
from semantic_memory_support import SemanticRoot  # noqa: E402

M12_IMPLEMENTED = (ITER_SRC / "tools" / "read_file.py").exists()
FILE_TOOLS = ["read_file", "write_file", "edit_file", "list_files", "grep_files"]
BUILD_TOOLS = FILE_TOOLS + ["run_tests"]


def pending(item):
    assert item.startswith("M12-"), item
    return unittest.expectedFailure


def require_m12():
    if not M12_IMPLEMENTED:
        raise AssertionError("Milestone 12 not implemented: iter/tools/read_file.py is missing")


class _Unimplemented:
    def start(self):
        return None

    def close(self):
        return None

    def __getattr__(self, name):
        require_m12()
        raise AttributeError(name)


def m12_root(name, with_main_js=False):
    """A throwaway ITER_DIR. With `with_main_js`, a `main.js` beside it makes the parent the repo root."""
    if not M12_IMPLEMENTED:
        return _Unimplemented()
    root = SemanticRoot(name)
    if with_main_js:
        (root.root.parent / "main.js").write_text("// repo root marker for tests\n", encoding="utf-8")
    return root


def run_tool(root, name, env=None, **kwargs):
    """Run tools/<name>.py run(**kwargs) in a fresh process from ITER_DIR, as the loop's worker does.

    Unlike SemanticRoot.tool, every keyword reaches the tool (shell's own `cwd` and `timeout` included), and
    the arguments travel in a file, so a 2 MB argument fits."""
    import json
    import subprocess
    import tempfile
    from semantic_memory_support import PYTHON, RUNNER
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(kwargs, handle)
        args_file = handle.name
    try:
        proc = subprocess.run([PYTHON, str(RUNNER), str(root.root / "tools" / (name + ".py")), "@" + args_file],
                              cwd=str(root.root), env=root.env(env), capture_output=True, text=True, timeout=600)
    finally:
        os.unlink(args_file)
    lines = proc.stdout.strip().splitlines()
    try:
        return json.loads(lines[-1])
    except Exception:
        return {"ok": False, "error": "runner crash", "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-3000:]}


def tool_text(root, name, **kwargs):
    """The tool's result text, or `RAISED <error>` when it raised."""
    result = run_tool(root, name, **kwargs)
    if result.get("ok"):
        return result.get("result")
    return "RAISED " + str(result.get("error"))


def agents_md():
    return (ITER_SRC / "AGENTS.md").read_text(encoding="utf-8")


def injected_agents_md():
    """What the model sees of AGENTS.md: the slice agents_md_inject.py takes."""
    source = (ITER_SRC / "transformations" / "agents_md_inject.py").read_text(encoding="utf-8")
    match = re.search(r"(?:MAX_CHARS|AGENTS_MD_MAX_CHARS|LIMIT)\s*=\s*(\d+)", source)
    limit = int(match.group(1)) if match else 6000
    return agents_md()[:limit]


def lifecycle_seed():
    return (ITER_SRC / "capability_lifecycle.metta").read_text(encoding="utf-8")


def gate_source():
    return (ITER_SRC / "tools" / "_metta_gate.py").read_text(encoding="utf-8")


def main_js():
    return (REPO / "main.js").read_text(encoding="utf-8")


def iter_py():
    return (ITER_SRC / "iter.py").read_text(encoding="utf-8")
