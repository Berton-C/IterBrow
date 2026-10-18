#!/usr/bin/env python3
"""M12-C1..C3: guidance that reaches the prompt — the "Building and changing code" section inside the
injected slice of AGENTS.md, one app-id rule, honest app opening, README rows.

Spec: docs/milestones/M12_builder_hands.md section C.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m12_support import pending, require_m12, agents_md, injected_agents_md, BUILD_TOOLS, ITER_SRC, REPO  # noqa: E402


class AgentsMdTests(unittest.TestCase):
    """M12-C1"""

    @pending("M12-C1")
    def test_building_section_lands_in_the_injected_slice(self):
        require_m12()
        seen = injected_agents_md()
        self.assertIn("## Building and changing code", seen)
        section = seen[seen.index("## Building and changing code"):]
        section = section[:section.index("\n## ", 1)] if "\n## " in section[1:] else section
        self.assertLessEqual(len(section), 1800, "the section fits the budget it was given")
        for name in BUILD_TOOLS + ["shell", "browser_eval"]:
            self.assertIn("`%s`" % name, section, name)
        for phrase in ("iter/<id>/index.html", "iter/apps/<id>/app.json", "Apps menu", "cwd", "timeout", "edit_file"):
            self.assertIn(phrase, section, phrase)

    @pending("M12-C1")
    def test_tool_table_names_every_tool_this_milestone_adds(self):
        text = agents_md()
        table = text[text.index("## Tool Inventory"):]
        for name in BUILD_TOOLS + ["python", "self_improve", "read_tool_result"]:
            self.assertRegex(table, r"^\| `%s`" % re.escape(name), name)
        tools = {p.stem for p in (ITER_SRC / "tools").glob("*.py") if not p.name.startswith("_")}
        for name in BUILD_TOOLS:
            self.assertIn(name, tools, name)
        reprogramming = (ITER_SRC / "reprogramming.txt").read_text(encoding="utf-8")
        self.assertIn("edit_file", reprogramming)


class AppIdTests(unittest.TestCase):
    """M12-C2"""

    @pending("M12-C2")
    def test_one_id_rule_and_honest_opening(self):
        require_m12()
        local = (ITER_SRC / "iterbrow_runtime" / "local_apps.py").read_text(encoding="utf-8")
        foundry = (ITER_SRC / "iterbrow_runtime" / "foundry_projects.py").read_text(encoding="utf-8")
        pattern = re.search(r're\.compile\(r?"(\^\[a-z\]\[a-z0-9-\]\{0,62\}\$)"\)', foundry)
        self.assertIsNotNone(pattern, "foundry's id regex is the reference")
        self.assertIn(pattern.group(1), local, "local_apps uses the same regex (no underscore)")
        main = (REPO / "main.js").read_text(encoding="utf-8")
        self.assertIn("/^[a-z][a-z0-9-]{0,62}$/", main[main.index("function plainAppDir"):main.index("function plainAppDir") + 600])
        apps = (ITER_SRC / "tools" / "apps.py").read_text(encoding="utf-8")
        self.assertNotIn("browser_new_tab", apps, "an ordinary tab has no app preload; do not send Iter there")
        self.assertIn("Apps menu", apps)


class ReadmeTests(unittest.TestCase):
    """M12-C3"""

    @pending("M12-C3")
    def test_readme_rows_match_the_code(self):
        require_m12()
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        row = next((line for line in readme.splitlines() if line.startswith("| `self_improve`")), "")
        self.assertNotIn("PWQ approval request", row)
        self.assertIn("ordinary loop", row)
        for name in BUILD_TOOLS:
            self.assertRegex(readme, r"^\| `%s`" % re.escape(name), name)


if __name__ == "__main__":
    unittest.main()
