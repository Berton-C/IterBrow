"""Authoritative read-only query boundary for the engineering governor."""

import sys
from pathlib import Path


TOOLS = str(Path(__file__).resolve().parents[1] / "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import _metta_substrate  # noqa: E402


def run_query(code):
    return _metta_substrate.run_query(code)
