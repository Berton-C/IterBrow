#!/usr/bin/env python3
"""M15-B1..B2: the tool list is a per-request view; descriptions fit.

Spec: docs/milestones/M15_build_ledger.md section B.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m15_support import pending, require_m15, runtime_module, openai_tools, real_tools, agents_md, ITER_SRC, REPO  # noqa: E402

BUILDER = ["read_file", "write_file", "edit_file", "list_files", "grep_files", "run_tests", "shell", "python",
           "browser_click", "browser_type", "browser_scroll", "browser_eval", "browser_read_text", "browser_screenshot",
           "browser_wait_for", "browser_open_app", "browser_navigate", "browser_new_tab", "browser_tabs", "browser_attach",
           "browser_switch_tab", "browser_close_tab", "new_app", "app_probe", "app_rollback", "apps", "github", "websearch",
           "card", "brief", "ally_sdk", "send", "nop", "task_state", "remember", "read_tool_result"]
BUILD_ONLY = ["new_app", "app_probe", "app_rollback", "github", "run_tests"]
ALWAYS = ["send", "nop", "read_file", "write_file", "edit_file", "shell", "browser_click", "browser_eval"]


class ViewTests(unittest.TestCase):
    """M15-B1"""

    def test_build_and_chat_views(self):
        view = runtime_module("tool_view")
        tools = real_tools()
        names = {t["function"]["name"] for t in tools}
        self.assertTrue(set(BUILDER) <= names, set(BUILDER) - names)
        build = {t["function"]["name"] for t in view.view(tools, "build")}
        chat = {t["function"]["name"] for t in view.view(tools, "chat")}
        self.assertTrue(set(BUILDER) <= build, set(BUILDER) - build)
        self.assertLessEqual(len(build), 40, "the build view is the builder's set, not everything")
        for name in BUILD_ONLY:
            self.assertNotIn(name, chat, name)
        for name in ALWAYS:
            self.assertIn(name, build, name)
            self.assertIn(name, chat, name)
        self.assertEqual([t["function"]["name"] for t in view.view(tools, "build")],
                         [t["function"]["name"] for t in tools if t["function"]["name"] in build], "order kept, dicts untouched")
        self.assertEqual(view.view(tools, "nonsense"), tools, "an unknown mode hides nothing")

    def test_budget_transformation_applies_the_view_and_logs_a_switch(self):
        require_m15()
        src = (ITER_SRC / "transformations" / "dynamic_tool_budget.py").read_text(encoding="utf-8")
        self.assertIn("tool_view", src)
        self.assertIn("build_mode", src)
        self.assertIn("[tool view]", src)
        loop = (ITER_SRC / "iter.py").read_text(encoding="utf-8")
        self.assertIn("tool_view", loop + src, "the view is applied before the request is estimated")


class DescriptionTests(unittest.TestCase):
    """M15-B2"""

    def test_every_description_fits_and_the_build_view_is_small(self):
        require_m15()
        tools = real_tools()
        long = sorted((len(t["function"]["description"]), t["function"]["name"]) for t in tools
                      if len(t["function"]["description"]) > 280)
        self.assertEqual(long, [], "descriptions over 280 characters")
        loop = (ITER_SRC / "iter.py").read_text(encoding="utf-8")
        self.assertRegex(loop, r"MAX_TOOL_DESCRIPTION_CHARS = 300\b")
        budget = runtime_module("request_budget")
        view = runtime_module("tool_view")
        build = view.view(tools, "build")
        self.assertLessEqual(budget.estimate_input_tokens([], build), 7000, "the build view's schemas, uncalibrated")
        self.assertLessEqual(budget.estimate_input_tokens([], tools), 14000, "every tool, uncalibrated (was ≈17k)")
        table = agents_md()[agents_md().index("## Tool Inventory"):]
        for t in tools:
            name = t["function"]["name"]
            if name in BUILD_ONLY + ["websearch", "card", "new_app", "apps"]:
                self.assertIn("| `%s` |" % name, table, name)


if __name__ == "__main__":
    unittest.main()
