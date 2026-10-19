#!/usr/bin/env python3
"""M14-C1..C4: new_app, the app contract, app_probe with the app's own probe.json, the build_watch note.

Spec: docs/milestones/M14_vault_and_foundry_loop.md section C.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m14_support import (pending, require_m14, vault_root, fake_bridge, transformation, agents_md,  # noqa: E402
                         assistant, tool_result, user, system, REPO, ITER_SRC)
from m6_support import run_playwright, playwright_available  # noqa: E402

PROBE = {"steps": [], "assertions": [{"kind": "text", "selector": "#title", "expected": "Todo"}]}


class NewAppTests(unittest.TestCase):
    """M14-C1"""

    def test_scaffold(self):
        r = vault_root("m14new", with_main_js=True)
        self.addCleanup(r.close)
        self.assertEqual(r.text("new_app", id="todo", title="Todo"),
                         "NEW-APP vault/todo: index.html, probe.json, README.md — open it with browser_open_app(todo)")
        folder = r.vault / "todo"
        html = (folder / "index.html").read_text(encoding="utf-8")
        self.assertTrue(html.lower().startswith("<!doctype html>"))
        self.assertIn("<title>Todo</title>", html)
        self.assertIn('data-iter-ready="false"', html)
        self.assertIn('id="title"', html)
        self.assertIn('id="app"', html)
        self.assertIn("dataset.iterReady = 'true'", html)
        self.assertIn("iter:todo:", html)
        self.assertNotRegex(html, r"https?://", "no external resources by default")
        probe = json.loads((folder / "probe.json").read_text(encoding="utf-8"))
        self.assertEqual(probe, {"steps": [], "assertions": [{"kind": "text", "selector": "#title", "expected": "Todo"}]})
        self.assertIn("Todo", (folder / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(r.snapshots("todo"), [], "scaffolding takes no snapshot")
        res = r.tool("new_app", id="todo", title="Again")
        self.assertEqual((res["result"], (res.get("execution") or {}).get("state")), ("EXISTS: vault/todo", "invalid_input"))
        self.assertEqual((r.vault / "todo" / "index.html").read_text(encoding="utf-8"), html, "never overwrites")
        self.assertEqual((r.tool("new_app", id="Bad Name", title="x").get("execution") or {}).get("state"), "invalid_input")
        r.set_vault(None)
        res = r.tool("new_app", id="other", title="x")
        self.assertEqual((res.get("execution") or {}).get("state"), "refused")

    def test_from_example_copies_the_example_and_adds_a_probe_only_when_missing(self):
        r = vault_root("m14fromex", with_main_js=True)
        self.addCleanup(r.close)
        (r.root / "mapstation").mkdir()
        (r.root / "mapstation" / "index.html").write_text("<!doctype html><title>Iter Map Station</title><h1 id='title'>Map</h1>", encoding="utf-8")
        (r.root / "mapstation" / "map.js").write_text("1", encoding="utf-8")
        (r.root / "mapstation" / ".secret").write_text("x", encoding="utf-8")
        out = r.text("new_app", id="mymap", title="My Map", from_example="mapstation")
        self.assertTrue(out.startswith("NEW-APP vault/mymap: "), out)
        self.assertEqual((r.vault / "mymap" / "map.js").read_text(encoding="utf-8"), "1")
        self.assertFalse((r.vault / "mymap" / ".secret").exists())
        self.assertTrue((r.vault / "mymap" / "probe.json").is_file(), "an example without a probe gets the scaffold's")
        (r.root / "nodequest").mkdir()
        (r.root / "nodequest" / "index.html").write_text("<!doctype html>", encoding="utf-8")
        (r.root / "nodequest" / "probe.json").write_text(json.dumps(PROBE), encoding="utf-8")
        r.text("new_app", id="quest2", title="Quest", from_example="nodequest")
        self.assertEqual(json.loads((r.vault / "quest2" / "probe.json").read_text(encoding="utf-8")), PROBE, "the example's own probe is kept")
        self.assertEqual((r.tool("new_app", id="x", title="x", from_example="nope").get("execution") or {}).get("state"), "invalid_input")

    @unittest.skipUnless(playwright_available(), "needs playwright")
    def test_the_scaffold_runs_and_sets_ready(self):
        r = vault_root("m14ready", with_main_js=True)
        self.addCleanup(r.close)
        r.text("new_app", id="todo", title="Todo")
        html = (r.vault / "todo" / "index.html").read_text(encoding="utf-8")
        script = """
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.set_content(%s); pg.wait_for_timeout(200)
    print(json.dumps({"ready": pg.evaluate("document.body.dataset.iterReady"), "title": pg.evaluate("document.querySelector('#title').textContent")})); b.close()
""" % json.dumps(html)
        got = json.loads(run_playwright(script).strip().splitlines()[-1])
        self.assertEqual(got, {"ready": "true", "title": "Todo"})


class ContractTests(unittest.TestCase):
    """M14-C2"""

    def test_contract_doc_exists_and_is_linked(self):
        require_m14()
        doc = (REPO / "docs" / "APP_CONTRACT.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(doc.splitlines()), 60)
        for word in ("index.html", "data-iter-ready", "probe.json", "localStorage", "iter:<id>:", "window.iterApp", "README"):
            self.assertIn(word, doc, word)
        self.assertIn("APP_CONTRACT.md", agents_md())


class ProbeSpecTests(unittest.TestCase):
    """M14-C3"""

    def test_app_probe_reads_the_apps_probe_json(self):
        r = vault_root("m14probe", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo", probe=PROBE)
        result = {"observations": [{"kind": "text", "selector": "#title", "expected": "Todo", "actual": "Todo", "passed": True}],
                  "passed": 1, "failed": 0, "ready": True, "title": "Todo"}
        with fake_bridge(r.iter, {"ok": True, "result": result}) as bridge:
            out = r.text("app_probe", app="todo", env=bridge.env)
            self.assertEqual(out.splitlines()[0], "PROBE todo (probe.json): 1 passed, 0 failed")
            self.assertEqual(bridge.requests[-1]["params"]["assertions"], PROBE["assertions"])
            self.assertEqual(bridge.requests[-1]["params"]["steps"], [])
            out = r.text("app_probe", app="todo", env=bridge.env, assertions=json.dumps([{"kind": "count", "selector": "li", "expected": 0}]))
            self.assertEqual(out.splitlines()[0], "PROBE todo: 1 passed, 0 failed", "given assertions win over probe.json")
        r.app("bare")
        res = r.tool("app_probe", app="bare")
        self.assertEqual(res["result"], "ERROR: no assertions given and vault/bare/probe.json is missing")
        self.assertEqual((res.get("execution") or {}).get("state"), "invalid_input")
        (r.vault / "bare" / "probe.json").write_text("{nope", encoding="utf-8")
        res = r.tool("app_probe", app="bare")
        self.assertIn("vault/bare/probe.json", res["result"])
        self.assertEqual((res.get("execution") or {}).get("state"), "invalid_input")
        (r.root / "plainapp").mkdir()
        (r.root / "plainapp" / "index.html").write_text("<!doctype html>", encoding="utf-8")
        (r.root / "plainapp" / "probe.json").write_text(json.dumps(PROBE), encoding="utf-8")
        with fake_bridge(r.iter, {"ok": True, "result": result}) as bridge:
            self.assertEqual(r.text("app_probe", app="plainapp", env=bridge.env).splitlines()[0], "PROBE plainapp (probe.json): 1 passed, 0 failed")


class BuildWatchTests(unittest.TestCase):
    """M14-C4"""

    def _messages(self, *tail):
        return [system(), user("make a todo app")] + list(tail)

    def test_note_when_an_app_changed_since_its_last_probe_and_the_turn_is_a_send(self):
        watch = transformation("build_watch")
        edited = [assistant(calls=[("c1", "edit_file", {"path": "vault/todo/index.html", "old": "a", "new": "b"})]),
                  tool_result("c1", "EDITED vault/todo/index.html (+1 −1 lines)")]
        sending = [assistant(calls=[("c2", "send", {"text": "Todo is done"})])]
        self.assertEqual(watch.note(self._messages(*edited, *sending)),
                         "[build: vault/todo changed since its last probe — app_probe(todo) before reporting]")
        probed = [assistant(calls=[("c3", "app_probe", {"app": "todo"})]), tool_result("c3", "PROBE todo (probe.json): 2 passed, 0 failed")]
        self.assertIsNone(watch.note(self._messages(*edited, *probed, *sending)), "probed after the change")
        self.assertIsNone(watch.note(self._messages(*edited)), "no send yet")
        self.assertIsNone(watch.note(self._messages(*probed, *edited, assistant(calls=[("c4", "read_file", {"path": "vault/todo/index.html"})]))), "the newest turn is not a send")
        self.assertIsNotNone(watch.note(self._messages(*probed, *edited, *sending)), "a probe before the change does not count")
        new = [assistant(calls=[("c5", "new_app", {"id": "notes", "title": "Notes"})]),
               tool_result("c5", "NEW-APP vault/notes: index.html, probe.json, README.md — open it with browser_open_app(notes)")]
        self.assertIn("vault/notes", watch.note(self._messages(*new, *sending)))
        failed = [assistant(calls=[("c6", "app_probe", {"app": "todo"})]), tool_result("c6", "PROBE todo (probe.json): 1 passed, 1 failed\n✗ text #title: expected 'Todo' got ''")]
        self.assertIsNone(watch.note(self._messages(*edited, *failed, *sending)), "a failed probe still counts as having probed; the model sees the result")

    def test_transform_appends_to_the_system_prompt_and_removes_nothing(self):
        watch = transformation("build_watch")
        edited = [assistant(calls=[("c1", "write_file", {"path": "vault/todo/app.js", "content": "1"})]),
                  tool_result("c1", "WROTE vault/todo/app.js (1 bytes, 1 lines)"),
                  assistant(calls=[("c2", "send", {"text": "done"})])]
        tools = [{"type": "function", "function": {"name": "send"}}, {"type": "function", "function": {"name": "app_probe"}}]
        messages, out_tools = watch.transform(self._messages(*edited), list(tools))
        self.assertEqual(out_tools, tools)
        self.assertTrue(messages[0]["content"].endswith("[build: vault/todo changed since its last probe — app_probe(todo) before reporting]"))
        self.assertEqual(messages[0]["content"].count("[build: vault/todo"), 1)
        again, _ = watch.transform(messages, list(tools))
        self.assertEqual(again[0]["content"].count("[build: vault/todo"), 1, "never doubled")
        untouched, _ = watch.transform(self._messages(), list(tools))
        self.assertEqual(untouched[0]["content"], "You are Iter.")
        src = (ITER_SRC / "transformations" / "build_watch.py").read_text(encoding="utf-8")
        self.assertNotRegex(src, r"tools\s*=\s*\[", "never removes a tool")
        self.assertIn("DESCRIPTION", src)


if __name__ == "__main__":
    unittest.main()
