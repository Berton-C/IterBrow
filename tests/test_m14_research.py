#!/usr/bin/env python3
"""M14-E1..E2: the github tool (search, tree, read) and a websearch that finds things.

Spec: docs/milestones/M14_vault_and_foundry_loop.md section E. Parsers run over fixtures in
tests/fixtures/m14/; the two live tests skip without network.
"""
import json
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m14_support import pending, require_m14, tool_module, tool_source, vault_root, FIXTURES, ITER_SRC  # noqa: E402


def online(host="api.github.com"):
    try:
        socket.create_connection((host, 443), timeout=3).close()
        return True
    except OSError:
        return False


class GithubToolTests(unittest.TestCase):
    """M14-E1"""

    def test_pure_helpers(self):
        gh = tool_module("github")
        self.assertEqual(gh.raw_url("alice/pomodoro", "src/app.js"), "https://raw.githubusercontent.com/alice/pomodoro/HEAD/src/app.js")
        tree = json.loads((FIXTURES / "github_tree.json").read_text(encoding="utf-8"))
        self.assertEqual(gh.parse_tree(tree), [("LICENSE", 1070), ("README.md", 1200), ("src/app.js", 987), ("src/index.html", 4321)])
        search = json.loads((FIXTURES / "github_search.json").read_text(encoding="utf-8"))
        lines = gh.format_search(search)
        self.assertEqual(lines[0], "alice/pomodoro ★1234 — A tiny pomodoro timer in vanilla JS (MIT) https://github.com/alice/pomodoro")
        self.assertEqual(lines[1], "bob/tomato ★56 — (no description) (no license) https://github.com/bob/tomato")
        self.assertTrue(gh.valid_repo("alice/pomodoro"))
        self.assertFalse(gh.valid_repo("alice"))
        self.assertFalse(gh.valid_repo("alice/pomodoro/x"))
        self.assertFalse(gh.valid_path("../etc/passwd"))
        self.assertTrue(gh.valid_path("src/app.js"))

    def test_tool_shape_and_input_errors(self):
        r = vault_root("m14gh")
        self.addCleanup(r.close)
        src = tool_source("github")
        for word in ("ideas", "README", "license", "RATE-LIMITED", "READ_WIRE_CHARS", "IterBrow"):
            self.assertIn(word, src, word)
        loop = (ITER_SRC / "iter.py").read_text(encoding="utf-8")
        read_tools = loop[loop.index("READ_TOOLS"):loop.index("}", loop.index("READ_TOOLS")) + 1]
        self.assertIn('"github"', read_tools)
        for kwargs in (dict(action="read", repo="alice", path="x"), dict(action="read", repo="a/b", path="../x"),
                       dict(action="nope", repo="a/b"), dict(action="search", query="")):
            res = r.tool("github", **kwargs)
            self.assertEqual((res.get("execution") or {}).get("state"), "invalid_input", (kwargs, res))

    @unittest.skipUnless(online(), "needs network")
    def test_live_search_tree_read(self):
        r = vault_root("m14ghlive")
        self.addCleanup(r.close)
        out = r.text("github", action="search", query="pomodoro timer vanilla js", max_results="3")
        if out.startswith("RATE-LIMITED"):
            self.skipTest(out)
        lines = out.splitlines()
        self.assertTrue(1 <= len(lines) <= 3, out)
        self.assertRegex(lines[0], r"^\S+/\S+ ★\d+ — .* https://github\.com/\S+/\S+$")
        tree = r.text("github", action="tree", repo="octocat/Hello-World")
        if tree.startswith("RATE-LIMITED"):
            self.skipTest(tree)  # a shared address can spend the hourly allowance; the rate limit is reported honestly
        self.assertRegex(tree, r"(?m)^README\s+\d+$")
        read = r.text("github", action="read", repo="octocat/Hello-World", path="README")
        if read.startswith("RATE-LIMITED"):
            self.skipTest(read)
        self.assertTrue(read.startswith("octocat/Hello-World:README (lines 1–"), read)
        self.assertRegex(read, r"(?m)^    1\| ")
        missing = r.tool("github", action="read", repo="octocat/Hello-World", path="nope.txt")
        self.assertEqual((missing.get("execution") or {}).get("state"), "invalid_input", missing)


class WebsearchTests(unittest.TestCase):
    """M14-E2"""

    def test_parse_ddg_html(self):
        ws = tool_module("websearch")
        results = ws.parse_ddg_html((FIXTURES / "ddg_html.html").read_text(encoding="utf-8"))
        self.assertEqual([r["url"] for r in results], ["https://pomofocus.io/", "https://en.wikipedia.org/wiki/Pomodoro_Technique", "https://tomato-timer.com/"])
        self.assertEqual(results[0]["title"], "Pomofocus - Pomodoro Timer")
        self.assertEqual(results[0]["snippet"], "An online Pomodoro Timer to boost your productivity.")
        self.assertEqual(results[2]["title"], "TomatoTimer")
        self.assertEqual(ws.parse_ddg_html((FIXTURES / "ddg_empty.html").read_text(encoding="utf-8")), [])
        self.assertEqual(ws.parse_ddg_html(""), [])

    def test_backends_and_the_honest_empty_result(self):
        src = tool_source("websearch")
        self.assertIn("html.duckduckgo.com/html/", src)
        self.assertIn("lite.duckduckgo.com/lite/", src)
        self.assertIn("NO RESULTS: ", src)
        self.assertNotIn("all backends returned no results", src)
        self.assertLess(src.index("html.duckduckgo.com"), src.index("api.duckduckgo.com"), "the HTML search runs first")
        self.assertNotIn("5-backend cascade", src)
        self.assertNotIn("CORS proxy", src)
        import importlib.util
        spec = importlib.util.spec_from_file_location("m14_ws_desc", ITER_SRC / "tools" / "websearch.py")
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(ITER_SRC))
        spec.loader.exec_module(module)
        self.assertIn("DuckDuckGo", module.DESCRIPTION)
        self.assertIn("NO RESULTS", module.DESCRIPTION)

    @unittest.skipUnless(online("html.duckduckgo.com"), "needs network")
    def test_live_general_query_has_results(self):
        self.assertIn("html.duckduckgo.com", tool_source("websearch"), "E2's backend (today's cascade sometimes answers too)")
        r = vault_root("m14wslive")
        self.addCleanup(r.close)
        out = r.text("websearch", query="pomodoro timer web app", max_results="5")
        self.assertFalse(out.startswith("RAISED"), out)
        if out.startswith("NO RESULTS"):
            self.skipTest("the search engines answered with nothing from this network: " + out)
        results = json.loads(out)
        self.assertGreaterEqual(len(results), 3, out)
        self.assertTrue(all(r["url"].startswith("http") for r in results))


if __name__ == "__main__":
    unittest.main()
