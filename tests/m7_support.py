"""Shared helpers for the Milestone 7 (Soul personality) tests. Spec: docs/milestones/M7_soul_personality.md.

Not a test module. `pending(item)` = unittest.expectedFailure until the item is implemented
(remove the decorator to activate the test). Service-backed tests use `m7_root`, which fails
fast without starting a service until iter/transformations/soul_taste.py exists.
"""
import importlib
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import (REPO, ITER_SRC, NODE, PATTERNS, PAIRS, FEATURES, node, run_bridge,  # noqa: E402,F401
                        playwright_available, run_playwright, sidebar_page_script, card, outbox_message,
                        read_manifest)

M7_IMPLEMENTED = (ITER_SRC / "transformations" / "soul_taste.py").exists()


def pending(item):
    assert item.startswith("M7-"), item
    return unittest.expectedFailure


def require_m7():
    if not M7_IMPLEMENTED:
        raise AssertionError("Milestone 7 not implemented: iter/transformations/soul_taste.py is missing")


class _Unimplemented:
    def start(self):
        return None

    def close(self):
        return None

    def __getattr__(self, name):
        require_m7()
        raise AttributeError(name)


def m7_root(name):
    """A SemanticRoot (real AtomSpace service + tool runner) once M7 exists; else the stand-in."""
    if not M7_IMPLEMENTED:
        return _Unimplemented()
    from semantic_memory_support import SemanticRoot
    return SemanticRoot(name)


def soul_lens():
    return importlib.import_module("iterbrow_runtime.soul_lens")


def soul_settings():
    return importlib.import_module("iterbrow_runtime.soul_settings")


def write_soul_settings(root, person, features=None, **profile):
    runtime = Path(root) / ".runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    people = {person: {"features": features or {}, **profile}}
    (runtime / "soul_settings.json").write_text(json.dumps({"schema_version": 1, "person": person, "people": people}))


def choice_atom(person, kind, card_id, pick, at=1700000000000):
    return '(soul-choice "%s" "%s" "%s" "%s" %d)' % (person, kind, card_id, pick, at)


def card_atoms(card_id, kind, person, choices, at=1700000000000):
    """Operations that write a card's metadata atoms the way the card tool does (M7-A1).
    choices: list of (choice_id, pattern_or_None, museum_id_or_None)."""
    ops = [{"op": "upsert", "key": "state:soul_card:%s" % card_id,
            "atom": '(soul-card "%s" "%s" "%s" %d)' % (card_id, kind, person, at)}]
    for choice_id, pattern, museum_id in choices:
        ops.append({"op": "upsert", "key": "state:soul_card_choice:%s:%s" % (card_id, choice_id),
                    "atom": '(soul-card-choice "%s" "%s" %s "%s")' % (card_id, choice_id, pattern or "none", museum_id or "-")})
    return ops


def seed_choice(root, person, kind, card_id, pick, choices, at=1700000000000):
    """Write a card's metadata and the person's choice straight into the authority."""
    root.call("transact", {"operations": card_atoms(card_id, kind, person, choices, at), "actor": "iter", "source": "card"})
    root.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_choice:%s" % card_id,
                                           "atom": choice_atom(person, kind, card_id, pick, at)}],
                           "actor": "person", "source": "sidebar"})


def run_transformation(root, name, messages=None, tools=None, env_extra=None):
    """Run one transformation module in a subprocess against `root` (an ITER_DIR); returns (messages, tools)."""
    import subprocess
    code = ("import sys, json, importlib.util; spec = importlib.util.spec_from_file_location('t', sys.argv[1]);"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
            "msgs, tools = m.transform(json.loads(sys.argv[2]), json.loads(sys.argv[3])); print(json.dumps([msgs, tools]))")
    path = Path(root) / "transformations" / name
    if not path.exists():
        path = ITER_SRC / "transformations" / name
    env = dict(os.environ, ITER_DIR=str(root), **(env_extra or {}))
    proc = subprocess.run([sys.executable, "-c", code, str(path), json.dumps(messages or [{"role": "system", "content": "base"}]),
                           json.dumps(tools or [])], cwd=str(root), env=env, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-3000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def stv(atom):
    import re
    match = re.search(r"\(stv ([0-9.]+) ([0-9.]+)\)", atom)
    return (float(match.group(1)), float(match.group(2))) if match else None


def taste_n(atom):
    import re
    return int(re.search(r"\)\s+(\d+)\)\s*$", atom).group(1))


def tool_entry(name, description="x"):
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object"}}}


def museum_save(root, label):
    """Save a museum entry inside `root` (ITER_DIR) and return its id."""
    import subprocess
    code = ("import sys, os; sys.path.insert(0, os.path.join(sys.argv[1], 'tools')); import _component_museum as m;"
            "print(m.save(sys.argv[2], source='tab_variant')['id'])")
    proc = subprocess.run([sys.executable, "-c", code, str(root), label], cwd=str(root),
                          env=dict(os.environ, ITER_DIR=str(root)), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip().splitlines()[-1]


def museum_get(root, comp_id):
    import subprocess
    code = ("import sys, os, json; sys.path.insert(0, os.path.join(sys.argv[1], 'tools')); import _component_museum as m;"
            "print(json.dumps(m.get(sys.argv[2])))")
    proc = subprocess.run([sys.executable, "-c", code, str(root), comp_id], cwd=str(root),
                          env=dict(os.environ, ITER_DIR=str(root)), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])
