#!/usr/bin/env python3
"""M14-H1..H3: what made Iter cycle on 2026-10-19 (Berton's activity log) — an open app tab that never showed
the edited file, `vault/…` paths that only the file tools understood, progress notes after progress notes.

Spec: docs/milestones/M14_vault_and_foundry_loop.md section H.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m14_support import (require_m14, vault_root, fake_bridge, bridge_call, transformation, main_js, assistant,  # noqa: E402
                         tool_result, user, system, NODE, REPO, BRIDGE)


@unittest.skipUnless(NODE, "needs node")
class StaleAppTabTests(unittest.TestCase):
    """M14-H1"""

    FAKE = """{
  activeId: 2, attachedId: null, attach(id) { this.attachedId = id; }, isLocked(id) { return id === 9; },
  tabs: new Map([[2, { id: 2, url: 'file:///v/todo/index.html', loadedAt: %d, appScope: { appId: 'todo' },
    view: { webContents: { reload() { this.reloads = (this.reloads || 0) + 1; } } } }]]),
  async awaitLoad(id, start) { const tab = this.tabs.get(id); if (start) start(tab.view.webContents); tab.loadedAt = Date.now(); return { url: tab.url, title: 'Todo' }; },
  reloads() { return this.tabs.get(2).view.webContents.reloads || 0; },
  list() { return []; },
}"""

    def _open(self, loaded_at, folder):
        apps = "{ open: async () => ({ appId: 'todo', tabId: 2, focused: true, dir: %s }) }" % json.dumps(str(folder))
        return bridge_call(self.FAKE % loaded_at, "openApp", {"appId": "todo"}, apps_js=apps)

    def test_focused_app_reloads_only_when_its_files_are_newer(self):
        require_m14()
        folder = Path(tempfile.mkdtemp(prefix="m14-stale-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        (folder / "index.html").write_text("<!doctype html>", encoding="utf-8")
        old = int((time.time() - 3600) * 1000)
        fresh = int((time.time() + 60) * 1000)
        stale = self._open(old, folder)
        self.assertTrue(stale["ok"], stale)
        self.assertTrue(stale["result"]["reloaded"], "the file is newer than the page: reloaded")
        self.assertNotIn("dir", stale["result"], "the folder is the bridge's business, not the tool's")
        current = self._open(fresh, folder)
        self.assertFalse(current["result"]["reloaded"], "nothing changed since the load: left alone")
        source = (BRIDGE / "browser_bridge_server.js").read_text(encoding="utf-8")
        self.assertIn("newestFileTime", source)
        self.assertIn("loadedAt", (BRIDGE / "tab_manager.js").read_text(encoding="utf-8"))
        main = main_js()
        open_app = main[main.index("async function openRegisteredApp("):main.index("async function inspectRegisteredApp(")]
        self.assertIn("dir", open_app, "openRegisteredApp tells the bridge the app's folder")

    def test_tool_says_it_reloaded(self):
        r = vault_root("m14reloadtool")
        self.addCleanup(r.close)
        with fake_bridge(r.iter, {"ok": True, "result": {"appId": "todo", "tabId": 2, "focused": True, "reloaded": True,
                                                      "url": "file:///v/todo/index.html"}}) as bridge:
            self.assertEqual(r.text("browser_open_app", env=bridge.env, app_id="todo"),
                             "app todo: tabId=2 reloaded (files changed since it loaded) file:///v/todo/index.html")
        with fake_bridge(r.iter, {"ok": True, "result": {"appId": "todo", "tabId": 2, "focused": True, "reloaded": False,
                                                      "url": "file:///v/todo/index.html"}}) as bridge:
            self.assertEqual(r.text("browser_open_app", env=bridge.env, app_id="todo"), "app todo: tabId=2 focused file:///v/todo/index.html")


class VaultLinkTests(unittest.TestCase):
    """M14-H2"""

    def test_shell_and_python_see_vault_paths(self):
        r = vault_root("m14link", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo", html="<!doctype html><title>linked</title>")
        self.assertTrue((r.root / "vault").is_symlink())
        out = r.text("shell", cmd="cat vault/todo/index.html && ls vault")
        self.assertIn("linked", out)
        self.assertIn("todo", out)
        self.assertNotIn("No such file", out)
        self.assertIn("linked", r.text("read_file", path="./vault/todo/index.html"), "the link spelled as a path works too")
        self.assertIn("vault/todo/index.html", r.text("read_file", path="./vault/todo/index.html").splitlines()[0])
        self.assertEqual(r.text("list_files", path="vault"), "vault/todo/")
        apps = r.text("apps")
        self.assertNotIn("vault (", apps, "the link is never an app")
        r.set_vault(None)
        self.assertFalse((r.root / "vault").exists())

    def test_main_js_keeps_the_link_and_git_ignores_it(self):
        require_m14()
        main = main_js()
        self.assertIn("function ensureVaultLink()", main)
        self.assertLess(main.index("ensureVaultLink();", main.index("async function createWindow()")),
                        main.index("await retirePreviousIter(ITER_DIR, pushLog);", main.index("async function createWindow()")), "at startup")
        use = main[main.index("async function useVault("):main.index("async function undoLastChange(")]
        self.assertIn("ensureVaultLink()", use, "after choosing")
        self.assertIn("isSymbolicLink", main[main.index("function ensureVaultLink()"):main.index("function ensureVaultLink()") + 900])
        self.assertIn("\niter/vault\n", (REPO / ".gitignore").read_text(encoding="utf-8"))
        shell = (REPO / "iter" / "tools" / "shell.py").read_text(encoding="utf-8")
        self.assertIn("vault/<app>", shell)


class TheatreNoteTests(unittest.TestCase):
    """M14-H3"""

    def test_two_sends_in_a_row_draw_the_note(self):
        mode = transformation("build_mode")
        base = [system(), user("build me a todo app")]
        send = lambda i: [assistant(calls=[(i, "send", {"text": "working on it"})]), tool_result(i, "SENT")]  # noqa: E731
        work = [assistant(calls=[("w", "edit_file", {"path": "vault/todo/index.html", "old": "a", "new": "b"})]),
                tool_result("w", "EDITED vault/todo/index.html (+1 −1 lines)")]
        self.assertIsNone(mode.theatre(base + send("1")), "one message is fine")
        self.assertEqual(mode.theatre(base + send("1") + send("2")), mode.THEATRE)
        self.assertIsNone(mode.theatre(base + send("1") + work + send("2")), "a result between them")
        self.assertIsNone(mode.theatre(base + send("1") + [user("ok")] + send("2")), "the person spoke between them")
        self.assertEqual(mode.theatre(base + send("1") + [assistant("thinking…")] + send("2")), mode.THEATRE)
        messages, _ = mode.transform(base + send("1") + send("2"), [])
        self.assertTrue(messages[0]["content"].endswith(mode.THEATRE))
        self.assertIn(mode.BUILD_LOOP, messages[0]["content"])
        quiet, _ = mode.transform([system(), user("what time is it?")] + send("1") + send("2"), [])
        self.assertNotIn("two messages", quiet[0]["content"], "only while building")


class EngineInPlaceTests(unittest.TestCase):
    """M14-I1: a transaction updates the in-process engine in place; reconstruction only at start or on doubt."""

    def _space(self, temp_path, fake_metta):
        import types
        from unittest import mock
        sys.path.insert(0, str(REPO / "iter"))
        import metta_server
        (temp_path / "seed.metta").write_text("(declared seed)\n", encoding="utf-8")
        manifest_path = temp_path / "state_manifest.json"
        manifest_path.write_text(json.dumps({"schema_version": 1, "entries": [{
            "path": "seed.metta", "role": "source_seed", "format": "metta", "portable": False, "reset": False, "owner": "test"}]}), encoding="utf-8")
        fake_hyperon = types.SimpleNamespace(MeTTa=fake_metta, Environment=type("E", (), {"custom_env": staticmethod(lambda **_k: None)}))
        patches = [mock.patch.dict(sys.modules, {"hyperon": fake_hyperon}),
                   mock.patch.object(metta_server, "ITER_DIR", temp_path),
                   mock.patch.object(metta_server, "MANIFEST_PATH", manifest_path),
                   mock.patch.object(metta_server, "STATE_DIR", temp_path / ".runtime" / "atomspace"),
                   mock.patch.object(metta_server, "WORKING_DIR", temp_path / ".runtime" / "work")]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        return metta_server.MettaSpace()

    def test_commits_do_not_reconstruct_and_the_engine_tracks_the_store(self):
        require_m14()
        from test_metta_service import FakeMeTTa
        temp = Path(tempfile.mkdtemp(prefix="m14-engine-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        FakeMeTTa.instances = []
        space = self._space(temp, FakeMeTTa)
        built = len(FakeMeTTa.instances)
        self.assertGreaterEqual(built, 1)
        tx = lambda i, ops: space.transact({"transaction_id": "tx-%d" % i, "actor": "t", "source": "u", "operations": ops})  # noqa: E731
        tx(1, [{"op": "add", "key": "a", "atom": "(fact a)"}, {"op": "add", "key": "b", "atom": "(fact b)"}])
        tx(2, [{"op": "replace", "key": "a", "atom": "(fact a2)"}, {"op": "remove", "key": "b"}, {"op": "upsert", "key": "c", "atom": "(fact c)"}])
        self.assertEqual(len(FakeMeTTa.instances), built, "no reconstruction for a commit")
        self.assertEqual(sorted(a for a in space.engine.atoms if a.startswith("(fact")), ["(fact a2)", "(fact c)"])
        self.assertEqual(space._engine_atoms, {"a": "(fact a2)", "c": "(fact c)"})

    def test_a_malformed_atom_still_aborts_and_the_next_commit_works(self):
        require_m14()
        from test_metta_service import FakeMeTTa

        class Strict(FakeMeTTa):
            def parse_all(self, code):
                if "(bad" in code:
                    raise ValueError("unbalanced")
                return super().parse_all(code)
        temp = Path(tempfile.mkdtemp(prefix="m14-engine-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        Strict.instances = []
        space = self._space(temp, Strict)
        with self.assertRaises(Exception):
            space.transact({"transaction_id": "bad", "actor": "t", "source": "u", "operations": [{"op": "add", "key": "x", "atom": "(bad"}]})
        self.assertNotIn("x", space.store.atoms, "aborted: the store did not take it")
        self.assertTrue(space.engine_available, "an engine is back after the abort")
        space.transact({"transaction_id": "good", "actor": "t", "source": "u", "operations": [{"op": "add", "key": "y", "atom": "(fine y)"}]})
        self.assertIn("(fine y)", space.engine.atoms)
        self.assertEqual(space._engine_atoms, {"y": "(fine y)"})


class EngineCostTests(unittest.TestCase):
    """M14-I2: with the real Hyperon and a store the size of Berton's, a commit stays well under a second."""

    def test_commit_cost_with_real_hyperon(self):
        require_m14()
        try:
            import hyperon  # noqa: F401
        except Exception:
            self.skipTest("hyperon is not importable here")
        from unittest import mock
        sys.path.insert(0, str(REPO / "iter"))
        import metta_server
        temp = Path(tempfile.mkdtemp(prefix="m14-enginecost-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        (temp / "seed.metta").write_text("(declared seed)\n", encoding="utf-8")
        manifest_path = temp / "state_manifest.json"
        manifest_path.write_text(json.dumps({"schema_version": 1, "entries": [{
            "path": "seed.metta", "role": "source_seed", "format": "metta", "portable": False, "reset": False, "owner": "test"}]}), encoding="utf-8")
        patches = [mock.patch.object(metta_server, "ITER_DIR", temp), mock.patch.object(metta_server, "MANIFEST_PATH", manifest_path),
                   mock.patch.object(metta_server, "STATE_DIR", temp / ".runtime" / "atomspace"),
                   mock.patch.object(metta_server, "WORKING_DIR", temp / ".runtime" / "work")]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        space = metta_server.MettaSpace()
        self.assertTrue(space.engine_available, space.engine_error)
        bulk = [{"op": "add", "key": "event:%05d" % i, "atom": "(event e%d (stv 0.%02d 0.9) \"some text about tool %d\")" % (i, i % 100, i)} for i in range(20000)]
        space.transact({"transaction_id": "bulk", "actor": "t", "source": "u", "operations": bulk})
        started = time.monotonic()
        for i in range(5):
            space.transact({"transaction_id": "small-%d" % i, "actor": "t", "source": "u",
                            "operations": [{"op": "upsert", "key": "state:tool_reliability:x", "atom": "(tool-reliability x (stv 0.%d 0.5) %d 1 0)" % (i, i)}]})
        per_commit = (time.monotonic() - started) / 5
        self.assertLess(per_commit, 0.75, "a one-atom commit over 20k atoms took %.2fs" % per_commit)


class IdleReannouncementTests(unittest.TestCase):
    """M14-J1/J2 (2026-10-19 run: 'Kanban is complete' sent seven times with nothing new from the person)."""

    def test_loop_tells_the_truth_after_a_reply(self):
        require_m14()
        src = (REPO / "iter" / "iter.py").read_text(encoding="utf-8")
        self.assertIn("def _last_turn_was_only_send(", src)
        self.assertIn("sends_since_input", src)
        self.assertIn("Do not send the same report again.", src)
        self.assertIn("nop(wait_seconds=0)", src)
        # The function, lifted out and run on its own.
        start = src.index("def _last_turn_was_only_send(")
        end = src.index("\ncycle_number = 0", start)
        namespace = {}
        exec(src[start:end], namespace)  # noqa: S102 — our own source
        last = namespace["_last_turn_was_only_send"]
        self.assertTrue(last([user("build"), assistant(calls=[("1", "send", {})]), tool_result("1", "SUCCESS")]))
        self.assertFalse(last([user("build"), assistant(calls=[("1", "send", {}), ("2", "nop", {})])]), "send plus other work is not idle")
        self.assertFalse(last([assistant(calls=[("1", "send", {})]), user("thanks")]), "the person spoke after it")
        self.assertFalse(last([user("build"), assistant(calls=[("1", "edit_file", {})])]))

    def test_send_result_counts_replies_since_the_person_spoke(self):
        r = vault_root("m14sendcount")
        self.addCleanup(r.close)
        ui = r.root / ".runtime" / "electron_ui"
        (ui / "inbox").mkdir(parents=True)
        (ui / "outbox").mkdir(parents=True)
        (ui / ".last_input_at").write_text("%f" % (time.time() - 60), encoding="utf-8")
        first = r.text("send", channel="electron_ui", content="report one")
        self.assertEqual(first, "SUCCESS", "the first reply is plain")
        second = r.text("send", channel="electron_ui", content="report again")
        self.assertTrue(second.startswith("SUCCESS — 2 messages sent since the person last spoke"), second)
        self.assertIn("nop wait_seconds=0", second)
        (ui / ".last_input_at").write_text("%f" % (time.time() + 1), encoding="utf-8")  # they spoke
        self.assertEqual(r.text("send", channel="electron_ui", content="fresh"), "SUCCESS")
        channel = (REPO / "iter" / "channels" / "electron_ui.py").read_text(encoding="utf-8")
        self.assertIn(".last_input_at", channel)
        manifest = json.loads((REPO / "iter" / "state_manifest.json").read_text(encoding="utf-8"))
        self.assertIn(".runtime/electron_ui/.last_input_at", [e["path"] for e in manifest["entries"]])


if __name__ == "__main__":
    unittest.main()
