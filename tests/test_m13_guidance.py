#!/usr/bin/env python3
"""M13-D1: guidance — open, wait, prove; the new tools in the tables.

Spec: docs/milestones/M13_builder_eyes.md section D.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m13_support import pending, require_m13, ITER_SRC, REPO  # noqa: E402
from m12_support import injected_agents_md, agents_md  # noqa: E402

NEW_TOOLS = ["browser_wait_for", "browser_open_app", "app_probe"]


class GuidanceTests(unittest.TestCase):
    """M13-D1"""

    def test_building_section_and_tables(self):
        require_m13()
        seen = injected_agents_md()
        section = seen[seen.index("## Building and changing code"):]
        section = section[:section.index("\n## ", 1)] if "\n## " in section[1:] else section
        self.assertLessEqual(len(section), 1800)
        for name in NEW_TOOLS:
            self.assertIn("`%s`" % name, section, name)
        self.assertIn("target", section)
        table = agents_md()[agents_md().index("## Tool Inventory"):]
        for name in NEW_TOOLS:
            self.assertRegex(table, r"(?m)^\| `%s`" % re.escape(name), name)
        tabs_row = next(line for line in table.splitlines() if line.startswith("| `browser_tabs`"))
        for word in ("target", "locked", "app"):
            self.assertIn(word, tabs_row, word)
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        for name in NEW_TOOLS:
            self.assertRegex(readme, r"(?m)^\| `%s`" % re.escape(name), name)
        tools = {p.stem for p in (ITER_SRC / "tools").glob("*.py") if not p.name.startswith("_")}
        for name in NEW_TOOLS:
            self.assertIn(name, tools, name)


if __name__ == "__main__":
    unittest.main()
