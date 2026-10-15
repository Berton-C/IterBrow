"""Shared helpers for the Milestone 5 knowledge-base tests (docs/milestones/M5_knowledge_base.md).

Not a test module (no test_ prefix). Imported by tests/test_kb_*.py.

`pending(item)` marks a test for a spec item that is not implemented yet. It
is `unittest.expectedFailure`, so the suite stays green while the item is
pending and turns red in two cases: the test fails after its decorator was
removed (regression) or it passes while still decorated (stale decorator).
Implementing an item means deleting its decorator.
"""
import importlib
import json
import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ITER_SRC = REPO / "iter"
if str(ITER_SRC) not in sys.path:
    sys.path.insert(0, str(ITER_SRC))


def pending(item):
    """Spec item `item` (e.g. "M5-A1") is not implemented yet."""
    assert item.startswith("M5-"), item
    return unittest.expectedFailure


M5_IMPLEMENTED = (ITER_SRC / "iterbrow_runtime" / "kb_terms.py").exists()


def require_m5():
    """Fail while the milestone is unimplemented (an expected failure under @pending)."""
    if not M5_IMPLEMENTED:
        raise AssertionError("Milestone 5 not implemented: iter/iterbrow_runtime/kb_terms.py is missing")


class _Unimplemented:
    """Stands in for a SemanticRoot while M5 is unimplemented: setUp must not raise
    (unittest.expectedFailure only covers the test body), so start/close are
    no-ops and any real use fails with the milestone message instead of
    starting a service for a test that cannot pass yet."""

    def start(self):
        return None

    def close(self):
        return None

    def __getattr__(self, name):
        require_m5()
        raise AttributeError(name)


def kb_root(name):
    """A SemanticRoot (real service) once M5 exists; otherwise the fail-fast stand-in."""
    if not M5_IMPLEMENTED:
        return _Unimplemented()
    from semantic_memory_support import SemanticRoot
    return SemanticRoot(name)


def kb_terms():
    """iterbrow_runtime.kb_terms (ImportError until M5-A is implemented)."""
    return importlib.import_module("iterbrow_runtime.kb_terms")


def kb_inference():
    return importlib.import_module("iterbrow_runtime.kb_inference")


def nal_revision(pairs):
    """Reference NAL revision fold (spec section C) used to compute expected values."""
    total_w = 0.0
    total_wf = 0.0
    for strength, confidence in pairs:
        w = confidence / (1.0 - confidence)
        total_w += w
        total_wf += w * strength
    return total_wf / total_w, min(0.99, total_w / (total_w + 1.0))


def kb_atoms(root, kind):
    """Authority atoms of one kb kind: statement | evidence | term."""
    return root.call("read_atoms", {"prefix": "state:kb_%s:" % kind})["atoms"]


def query(root, code, view="current"):
    """Evaluate MeTTa against the test root's service; returns the result text."""
    return root.call("query", {"code": code, "view": view}, timeout=60)["result"]


def transact(root, operations, actor="test", source="test"):
    return root.call("transact", {"operations": operations, "actor": actor, "source": source})


def stv_of(text):
    """All (stv f c) pairs in a MeTTa result string, as floats."""
    import re
    return [(float(f), float(c)) for f, c in re.findall(r"\(stv\s+([-+\d.eE]+)\s+([-+\d.eE]+)\)", text)]


def close(a, b, places=3):
    return all(math.isclose(x, y, abs_tol=10 ** -places) for x, y in zip(a, b)) and len(a) == len(b)


def memory_metadata(root, item_id):
    document, metadata = root.memories()[item_id]
    return metadata


def legacy_memory_atom(item_id, document, metadata):
    """A semantic-memory atom exactly as _petta_db writes it (for backfill tests)."""
    from iterbrow_runtime.cognitive_events import metta_string
    return "(semantic-memory %s %s %s)" % (
        metta_string(item_id), metta_string(document),
        metta_string(json.dumps(metadata, sort_keys=True, ensure_ascii=False)))
