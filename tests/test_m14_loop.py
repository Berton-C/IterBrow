#!/usr/bin/env python3
"""M14-D1..D4: build mode and the foundry loop text, guidance, the new tools never hidden.

Spec: docs/milestones/M14_vault_and_foundry_loop.md section D.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m14_support import (pending, require_m14, transformation, agents_md, injected_agents_md, assistant, tool_result,  # noqa: E402
                         user, system, NEW_TOOLS, ITER_SRC, REPO)


class BuildModeTests(unittest.TestCase):
    """M14-D1"""

    def test_active_from_recent_calls_or_the_persons_words(self):
        mode = transformation("build_mode")
        quiet = [system(), user("what time is it in Goa?"), assistant("It is 11:02.")]
        self.assertFalse(mode.active(quiet))
        self.assertTrue(mode.active([system(), user("Build me a todo app")]))
        self.assertTrue(mode.active([system(), user("make me something for my recipes")]))
        self.assertTrue(mode.active([system(), user("what is in my vault?")]))
        self.assertFalse(mode.active([system(), user("I applied for a job")]), "whole words only: 'applied' is not 'app'")
        self.assertTrue(mode.active(quiet + [assistant(calls=[("c1", "new_app", {"id": "x", "title": "x"})])]))
        self.assertTrue(mode.active(quiet + [assistant(calls=[("c1", "read_file", {"path": "vault/todo/index.html"})])]))
        self.assertFalse(mode.active(quiet + [assistant(calls=[("c1", "read_file", {"path": "tools/send.py"})])]))
        old = [system(), user("build me a todo app")] + [assistant("…"), user("thanks")] * 9
        self.assertFalse(mode.active(old), "only the last 16 messages count")

    def test_transform_appends_the_loop_only_when_active(self):
        mode = transformation("build_mode")
        self.assertLessEqual(len(mode.BUILD_LOOP), 1100)
        tools = [{"type": "function", "function": {"name": "send"}}]
        messages, out = mode.transform([system(), user("build me a todo app")], list(tools))
        self.assertTrue(messages[0]["content"].endswith(mode.BUILD_LOOP))
        self.assertEqual(out, tools)
        again, _ = mode.transform(messages, list(tools))
        self.assertEqual(again[0]["content"].count(mode.BUILD_LOOP), 1)
        quiet, _ = mode.transform([system(), user("what time is it?")], list(tools))
        self.assertEqual(quiet[0]["content"], "You are Iter.")


class LoopTextTests(unittest.TestCase):
    """M14-D2"""

    def test_the_five_steps_and_the_one_rule(self):
        text = transformation("build_mode").BUILD_LOOP
        order = [text.index(w) for w in ("Research", "Propose", "Build", "Prove", "Report")]
        self.assertEqual(order, sorted(order), "research, propose, build, prove, report — in that order")
        for word in ('websearch(source="github")', "github", "card(kind=\"fork\")", "pattern", "[choice card=",
                     "new_app", "vault/<id>/", "probe.json", "browser_open_app", "browser_wait_for", "app_probe(<id>)",
                     "browser_click", "card(kind=\"offer\")", "brief", "ally_sdk"):
            self.assertIn(word, text, word)
        self.assertRegex(text, r"never report a probe you did not run")
        self.assertRegex(text, r"never a progress note")
        self.assertNotRegex(text, r"(?i)must not send|cannot send|refuse", "a rule for the model, never a gate")


class GuidanceTests(unittest.TestCase):
    """M14-D3"""

    def test_building_section_and_tables(self):
        require_m14()
        seen = injected_agents_md()
        section = seen[seen.index("## Building and changing code"):]
        section = section[:section.index("\n## ", 1)] if "\n## " in section[1:] else section
        self.assertLessEqual(len(section), 1800)
        for word in ("vault/<id>/", "`new_app`", "`app_rollback`", "probe.json", "progress"):
            self.assertIn(word, section, word)
        table = agents_md()[agents_md().index("## Tool Inventory"):]
        for name in NEW_TOOLS:
            self.assertRegex(table, r"(?m)^\| `%s`" % re.escape(name), name)
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        for name in NEW_TOOLS:
            self.assertRegex(readme, r"(?m)^\| `%s`" % re.escape(name), name)
        self.assertIn("Where apps live", readme)
        tools = {p.stem for p in (ITER_SRC / "tools").glob("*.py") if not p.name.startswith("_")}
        for name in NEW_TOOLS:
            self.assertIn(name, tools, name)
        for name in ("app_probe", "apps", "websearch"):  # rows regenerated from the new descriptions
            row = next(line for line in table.splitlines() if line.startswith("| `%s`" % name))
            import importlib.util
            spec = importlib.util.spec_from_file_location("m14_desc_" + name, ITER_SRC / "tools" / (name + ".py"))
            module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(ITER_SRC))
            spec.loader.exec_module(module)
            self.assertIn(module.DESCRIPTION.split(".")[0][:60], row, name)


class NeverHiddenTests(unittest.TestCase):
    """M14-D4"""

    def test_protected_in_both_lists(self):
        require_m14()
        budget = (ITER_SRC / "transformations" / "dynamic_tool_budget.py").read_text(encoding="utf-8")
        block = budget[budget.index("PROTECTED_TOOLS"):budget.index("}", budget.index("PROTECTED_TOOLS")) + 1]
        loop = (ITER_SRC / "iter.py").read_text(encoding="utf-8")
        start = loop.index("PROTECTED_TOOL_NAMES = {")  # the definition, not an earlier comment
        names = loop[start:loop.index("}", start) + 1]
        for name in NEW_TOOLS:
            self.assertIn('"%s"' % name, block, name)
            self.assertIn('"%s"' % name, names, name)


if __name__ == "__main__":
    unittest.main()
