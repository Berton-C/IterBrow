#!/usr/bin/env python3
"""The loader's tool cap never drops a tool silently (regression guard, 2026-10-19).

iter.py loads at most MAX_TOOLS - 1 tools from tools/ (plus the host's read_tool_result), protected ones first,
the rest alphabetically; anything past the cap disappears from the model's tool list. That hid `send` once and
`write_file` after M13 added three tools. This fails the moment the next tool would cross the cap.
"""
import re
import unittest
from pathlib import Path

ITER = Path(__file__).resolve().parents[1] / "iter"


class ToolCapTests(unittest.TestCase):
    def test_every_public_tool_fits_under_the_cap(self):
        source = (ITER / "iter.py").read_text(encoding="utf-8")
        cap = int(re.search(r"^MAX_TOOLS = (\d+)", source, re.M).group(1))
        public = sorted(p.stem for p in (ITER / "tools").glob("*.py") if not p.name.startswith("_") and p.stem != "read_tool_result")
        self.assertLessEqual(len(public), cap - 1, "%d public tools, cap allows %d: raise MAX_TOOLS or retire a tool" % (len(public), cap - 1))

    def test_protected_tools_exist(self):
        source = (ITER / "iter.py").read_text(encoding="utf-8")
        block = source[source.index("PROTECTED_TOOL_NAMES = {"):source.index("}", source.index("PROTECTED_TOOL_NAMES = {")) + 1]
        names = re.findall(r'"([a-z_]+)"', block)
        tools = {p.stem for p in (ITER / "tools").glob("*.py")} | {"read_tool_result"}
        self.assertEqual([n for n in names if n not in tools], [], "a protected name with no tool behind it")


if __name__ == "__main__":
    unittest.main()
