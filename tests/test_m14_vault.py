#!/usr/bin/env python3
"""M14-A1..A5: the vault — a folder the person chose, the catalog, the file tools reaching it, the Apps menu.

Spec: docs/milestones/M14_vault_and_foundry_loop.md section A.
"""
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m14_support import (pending, require_m14, vault_root, vault_module, menu_template, main_js, runtime_source,  # noqa: E402
                         EXAMPLES, ITER_SRC, REPO, NODE, BRIDGE)
from semantic_memory_support import PYTHON  # noqa: E402


class VaultModuleTests(unittest.TestCase):
    """M14-A1"""

    def test_path_reads_settings_each_time_and_never_raises(self):
        r = vault_root("m14path")
        self.addCleanup(r.close)
        vault = vault_module()
        settings = r.root / ".runtime" / "settings.json"
        self.assertEqual(vault.path(settings), Path(os.path.realpath(r.vault)))
        r.set_vault(None)
        self.assertIsNone(vault.path(settings), "unset")
        r.set_vault(r.vault / "missing")
        self.assertIsNone(vault.path(settings), "not a directory")
        link = r.vault.parent / "vault-link"
        os.symlink(r.vault, link)
        r.set_vault(link)
        self.assertIsNone(vault.path(settings), "a symlink is not a vault")
        settings.write_text("{not json", encoding="utf-8")
        self.assertIsNone(vault.path(settings), "bad settings never raise")
        settings.unlink()
        self.assertIsNone(vault.path(settings), "no settings file")

    def test_apps_lists_real_app_folders_only(self):
        r = vault_root("m14apps")
        self.addCleanup(r.close)
        vault = vault_module()
        r.app("todo", brief={"for": "me", "flourishing": "done lists"})
        r.app("notes")
        (r.vault / ".iter").mkdir()
        (r.vault / ".iter" / "index.html").write_text("x", encoding="utf-8")
        (r.vault / "Bad Name").mkdir()
        (r.vault / "Bad Name" / "index.html").write_text("x", encoding="utf-8")
        (r.vault / "empty").mkdir()
        os.symlink(r.vault / "todo", r.vault / "linked")
        apps = vault.apps(r.vault)
        self.assertEqual([a["id"] for a in apps], ["notes", "todo"])
        todo = apps[1]
        self.assertEqual((todo["entry"], todo["brief"]["for"]), ("index.html", "me"))
        self.assertEqual(Path(todo["path"]), r.vault / "todo")
        self.assertIsNone(apps[0]["brief"])
        self.assertEqual(vault.app_dir("todo", r.vault), r.vault / "todo")
        self.assertIsNone(vault.app_dir("linked", r.vault))
        self.assertIsNone(vault.app_dir(".iter", r.vault))
        self.assertIsNone(vault.app_dir("empty", r.vault))

    def test_copy_examples_once_never_overwriting(self):
        r = vault_root("m14examples")
        self.addCleanup(r.close)
        vault = vault_module()
        self.assertEqual(tuple(vault.EXAMPLES), EXAMPLES)
        for name in EXAMPLES:
            self.assertTrue((ITER_SRC / name / "index.html").is_file(), name)
        r.app("mapstation", html="<!doctype html><title>mine</title>")  # the person's own copy already there
        copied = vault.copy_examples(r.vault, ITER_SRC)
        self.assertEqual(copied, ["nodequest"])
        self.assertEqual((r.vault / "mapstation" / "index.html").read_text(encoding="utf-8"), "<!doctype html><title>mine</title>")
        self.assertTrue((r.vault / "nodequest" / "index.html").is_file())
        self.assertFalse(any(p.name.startswith(".") for p in (r.vault / "nodequest").rglob("*")), "no dot-files copied")
        marker = json.loads((r.vault / ".iter" / "examples.json").read_text(encoding="utf-8"))
        self.assertIn("nodequest", marker["copied"])
        import shutil
        shutil.rmtree(r.vault / "nodequest")
        self.assertEqual(vault.copy_examples(r.vault, ITER_SRC), [], "a deleted copy is not recreated")
        self.assertFalse((r.vault / "crm").exists())

    def test_cli_prints_json(self):
        r = vault_root("m14cli")
        self.addCleanup(r.close)
        r.app("todo")
        env = dict(os.environ, ITER_DIR=str(r.root))
        out = subprocess.run([PYTHON, "-m", "iterbrow_runtime.vault", "path"], cwd=str(r.root), env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(out.stdout.strip().splitlines()[-1]), str(Path(os.path.realpath(r.vault))), out.stderr)
        out = subprocess.run([PYTHON, "-m", "iterbrow_runtime.vault", "apps"], cwd=str(r.root), env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual([a["id"] for a in json.loads(out.stdout.strip().splitlines()[-1])], ["todo"])
        self.assertNotIn("ITER_VAULT", runtime_source("vault"), "the vault is read from settings, never an env variable")


class CatalogTests(unittest.TestCase):
    """M14-A2"""

    def test_catalog_puts_vault_apps_first_and_hides_same_named_plain_apps(self):
        r = vault_root("m14catalog")
        self.addCleanup(r.close)
        r.app("todo", brief={"for": "the family", "flourishing": "nothing forgotten"})
        r.app("mapstation", html="<!doctype html><title>vault map</title>")
        (r.root / "mapstation").mkdir()
        (r.root / "mapstation" / "index.html").write_text("<!doctype html><title>shipped</title>", encoding="utf-8")
        (r.root / "nodequest").mkdir()
        (r.root / "nodequest" / "index.html").write_text("<!doctype html>", encoding="utf-8")
        env = dict(os.environ, ITER_DIR=str(r.root))
        out = subprocess.run([PYTHON, "-m", "iterbrow_runtime.local_apps"], cwd=str(r.root), env=env,
                             capture_output=True, text=True, timeout=60)
        apps = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual([(a["id"], a["kind"]) for a in apps], [("mapstation", "vault"), ("todo", "vault"), ("nodequest", "plain")], apps)
        self.assertEqual(Path(apps[0]["path"]), r.vault / "mapstation")
        self.assertEqual(apps[1]["brief"]["for"], "the family")
        self.assertEqual(r.text("apps").splitlines()[1], "todo (vault) %s — for the family" % (r.vault / "todo" / "index.html").resolve().as_uri())

    def test_brief_and_ally_find_the_vault_app_first(self):
        r = vault_root("m14brief")
        self.addCleanup(r.close)
        r.app("todo")
        (r.root / "todo").mkdir()
        (r.root / "todo" / "index.html").write_text("<!doctype html>", encoding="utf-8")
        self.assertEqual(r.text("brief", app="todo", for_whom="the family", flourishing="nothing forgotten"), "BRIEF-SAVED: todo")
        self.assertTrue((r.vault / "todo" / "brief.json").is_file(), "the brief lands in the vault app")
        self.assertFalse((r.root / "todo" / "brief.json").exists())
        self.assertEqual(r.text("ally_sdk", app="todo"), "ALLY-SDK: installed in todo")
        self.assertTrue((r.vault / "todo" / "iter_ally.js").is_file())


class FileToolsTests(unittest.TestCase):
    """M14-A3"""

    def test_vault_spelling_resolves_and_prints_back(self):
        r = vault_root("m14files", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo")
        self.assertEqual(r.text("write_file", path="vault/todo/app.js", content="console.log(1)\n"), "WROTE vault/todo/app.js (15 bytes, 1 lines)")
        self.assertEqual((r.vault / "todo" / "app.js").read_text(encoding="utf-8"), "console.log(1)\n")
        self.assertEqual(r.text("read_file", path="vault/todo/app.js").splitlines()[0], "vault/todo/app.js (lines 1–1 of 1)")
        self.assertEqual(r.text("edit_file", path="vault/todo/app.js", old="log(1)", new="log(2)").splitlines()[0], "EDITED vault/todo/app.js (+1 −1 lines)")
        self.assertEqual(r.text("list_files", path="vault"), "vault/todo/")
        self.assertEqual(r.text("grep_files", pattern="log", path="vault/todo"), "vault/todo/app.js:1: console.log(2)")
        absolute = str(r.vault / "todo" / "index.html")
        self.assertIn("vault/todo/index.html (lines", r.text("read_file", path=absolute), "an absolute path inside the vault is fine and shown as vault/")
        self.assertIn("todo", r.text("shell", cmd="pwd", cwd="vault/todo"))
        self.assertIn("lines 1–", r.text("read_file", path="../main.js"), "the repo is still in scope")

    def test_refusals(self):
        r = vault_root("m14refuse", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo")
        res = r.tool("write_file", path="vault/.iter/snapshots/x", content="x")
        self.assertTrue(res["result"].startswith("REFUSED:"), res)
        self.assertEqual((res.get("execution") or {}).get("state"), "refused")
        self.assertTrue(r.text("read_file", path=str(r.vault.parent / "elsewhere.txt")).startswith("REFUSED:"), "beside the vault is outside every root")
        r.set_vault(None)
        res = r.tool("read_file", path="vault/todo/index.html")
        self.assertEqual(res["result"], "REFUSED: no apps folder chosen yet (Apps ▸ Choose apps folder…)")
        self.assertEqual((res.get("execution") or {}).get("state"), "refused")
        self.assertTrue(r.text("list_files", path="vault").startswith("REFUSED: no apps folder"))


@unittest.skipUnless(NODE, "needs node")
class AppsMenuTests(unittest.TestCase):
    """M14-A4"""

    CATALOG = [{"id": "todo", "kind": "vault", "path": "/v/todo", "entry": "index.html", "brief": {"for": "the family", "flourishing": "x"}},
               {"id": "notes", "kind": "vault", "path": "/v/notes", "entry": "index.html", "brief": None},
               {"id": "crm", "kind": "plain", "path": "/i/crm", "entry": "index.html", "brief": None},
               {"id": "mapstation", "kind": "plain", "path": "/i/mapstation", "entry": "index.html", "brief": None}]

    def test_menu_with_a_vault(self):
        require_m14()
        items = menu_template(self.CATALOG, {"vault": "/v", "recentVaults": ["/old"], "undoable": []})
        labels = [i.get("label") or i.get("type") for i in items]
        self.assertEqual(labels[:3], ["todo — for the family", "notes", "separator"])
        self.assertEqual(items[0]["click"], "open:todo")
        examples = next(i for i in items if i.get("label") == "Examples")
        self.assertEqual([s["label"] for s in examples["submenu"]], ["crm", "mapstation"])
        self.assertEqual(examples["submenu"][1]["click"], "open:mapstation")
        self.assertIn("Choose apps folder…", labels)
        self.assertEqual(next(i for i in items if i.get("label") == "Choose apps folder…")["click"], "choose")
        self.assertEqual(next(i for i in items if i.get("label") == "Reveal apps folder")["click"], "reveal")
        recent = next(i for i in items if i.get("label") == "Recent")
        self.assertEqual([(s["label"], s["click"]) for s in recent["submenu"]], [("/old", "switch:/old")])

    def test_menu_without_a_vault_shows_only_examples_and_choose(self):
        require_m14()
        items = menu_template(self.CATALOG[2:], {"vault": None, "recentVaults": [], "undoable": []})
        labels = [i.get("label") for i in items if i.get("label")]
        self.assertEqual(labels, ["Examples", "Choose apps folder…"])
        self.assertNotIn("Reveal apps folder", labels)
        self.assertNotIn("Recent", labels)

    def test_main_js_opens_vault_apps_from_their_folder(self):
        require_m14()
        main = main_js()
        self.assertIn("require('./bridge/vault_menu')", main)
        self.assertRegex(main, r"function vaultAppDir\(")
        self.assertIn("openDirectory", main)
        self.assertIn("createDirectory", main)
        self.assertIn("recentVaults", main)
        self.assertIn("copy-examples", main)
        self.assertIn("[vault] ", main)
        open_app = main[main.index("async function openRegisteredApp("):main.index("async function inspectRegisteredApp(")]
        self.assertLess(open_app.index("vaultAppDir("), open_app.index("plainAppDir("), "the vault is checked before iter/")
        registered = main[main.index("function registeredAppForUrl("):main.index("function plainAppDir(")]
        self.assertIn("vault", registered.lower(), "a URL inside the vault maps back to its app id")
        self.assertNotIn("ITER_VAULT", main, "no env; the vault is settings.vault")


class SettingsTests(unittest.TestCase):
    """M14-A5"""

    def test_settings_show_the_vault_but_never_set_it(self):
        require_m14()
        html = (REPO / "renderer" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="setting-vault"', html)
        self.assertIn('id="btn-choose-vault"', html)
        main = main_js()
        load = main[main.index("ipcMain.handle('settings:load'"):main.index("ipcMain.handle('settings:save'")]
        self.assertIn("vault", load)
        save = main[main.index("ipcMain.handle('settings:save'"):main.index("ipcMain.handle('settings:save'") + 800]
        self.assertRegex(save, r"vault", "settings:save keeps the stored vault (the chooser is the only writer)")


if __name__ == "__main__":
    unittest.main()
