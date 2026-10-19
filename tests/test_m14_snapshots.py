#!/usr/bin/env python3
"""M14-B1..B4: snapshots before every file-tool write in the vault, one-action rollback, pruning, the
person's Undo in the Apps menu.

Spec: docs/milestones/M14_vault_and_foundry_loop.md section B.
"""
import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m14_support import pending, require_m14, vault_root, vault_module, menu_template, main_js, NODE  # noqa: E402

STAMP = re.compile(r"^\d{8}T\d{6}\d{6}Z__index\.html$")


class SnapshotTests(unittest.TestCase):
    """M14-B1"""

    def test_write_and_edit_snapshot_the_previous_content(self):
        r = vault_root("m14snap", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo", html="<!doctype html><title>v1</title>\n")
        self.assertEqual(r.text("write_file", path="vault/todo/index.html", content="<!doctype html><title>v2</title>\n"),
                         "WROTE vault/todo/index.html (33 bytes, 1 lines)")
        self.assertEqual(r.text("edit_file", path="vault/todo/index.html", old="v2", new="v3").splitlines()[0],
                         "EDITED vault/todo/index.html (+1 −1 lines)")
        self.assertEqual(r.text("write_file", path="vault/todo/index.html", content="<!doctype html><title>v3</title>\n"),
                         "WROTE vault/todo/index.html (unchanged)")
        entries = r.snapshots("todo")
        self.assertEqual([(e["file"], e["reason"], e["bytes"]) for e in entries],
                         [("index.html", "write_file", 33), ("index.html", "edit_file", 33)], "the unchanged write took no snapshot")
        store = r.vault / ".iter" / "snapshots" / "todo"
        for entry in entries:
            self.assertRegex(entry["stored"], STAMP)
            self.assertTrue((store / entry["stored"]).is_file())
        self.assertEqual((store / entries[0]["stored"]).read_text(encoding="utf-8"), "<!doctype html><title>v1</title>\n")
        self.assertEqual((store / entries[1]["stored"]).read_text(encoding="utf-8"), "<!doctype html><title>v2</title>\n")
        self.assertRegex(entries[0]["at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def test_a_new_file_logs_a_null_snapshot_and_nothing_happens_outside_the_vault(self):
        r = vault_root("m14snapnew", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo")
        r.text("write_file", path="vault/todo/styles.css", content="body{}\n")
        entries = r.snapshots("todo")
        self.assertEqual([(e["file"], e["bytes"], e["stored"]) for e in entries], [("styles.css", None, None)])
        r.text("write_file", path="scratch/note.txt", content="x\n")
        r.text("edit_file", path="scratch/note.txt", old="x", new="y")
        self.assertEqual(sorted(p.name for p in (r.vault / ".iter" / "snapshots").iterdir()), ["todo"], "no snapshot store for repo files")
        self.assertFalse((r.root / ".iter").exists())


class AllySdkSnapshotTests(unittest.TestCase):
    """M14-B1 (audit 2026-10-19): ally_sdk's change to a vault app's index.html is undoable too."""

    def test_ally_install_is_snapshotted(self):
        r = vault_root("m14ally", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo", html="<!doctype html><title>t</title><body></body>\n", brief={"for": "me", "flourishing": "x"})
        self.assertEqual(r.text("ally_sdk", app="todo"), "ALLY-SDK: installed in todo")
        files = sorted(e["file"] for e in r.snapshots("todo"))
        self.assertIn("index.html", files)
        self.assertTrue(all(e["reason"] == "ally_sdk" for e in r.snapshots("todo")))
        out = r.text("app_rollback", app="todo", steps=str(len(files)))
        self.assertIn("ROLLED BACK todo: index.html (to ", out)
        self.assertEqual((r.vault / "todo" / "index.html").read_text(encoding="utf-8"), "<!doctype html><title>t</title><body></body>\n")
        self.assertFalse((r.vault / "todo" / "iter_ally.js").exists(), "the SDK files a change created are gone too")


class RollbackTests(unittest.TestCase):
    """M14-B2"""

    def test_rollback_restores_newest_first_and_deletes_created_files(self):
        r = vault_root("m14roll", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo", html="<!doctype html><title>v1</title>\n")
        r.text("write_file", path="vault/todo/index.html", content="<!doctype html><title>v2</title>\n")
        r.text("write_file", path="vault/todo/app.js", content="1\n")
        r.text("edit_file", path="vault/todo/index.html", old="v2", new="v3")
        out = r.text("app_rollback", app="todo")
        self.assertRegex(out, r"^ROLLED BACK todo: index\.html \(to \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^)]*\)$")
        self.assertEqual((r.vault / "todo" / "index.html").read_text(encoding="utf-8"), "<!doctype html><title>v2</title>\n")
        out = r.text("app_rollback", app="todo", steps="2")
        lines = out.splitlines()
        self.assertEqual(lines[0], "ROLLED BACK todo: app.js (deleted)")
        self.assertTrue(lines[1].startswith("ROLLED BACK todo: index.html (to "))
        self.assertFalse((r.vault / "todo" / "app.js").exists())
        self.assertEqual((r.vault / "todo" / "index.html").read_text(encoding="utf-8"), "<!doctype html><title>v1</title>\n")
        self.assertEqual(r.snapshots("todo"), [], "consumed entries leave the log")
        self.assertEqual(r.text("app_rollback", app="todo"), "NOTHING TO ROLL BACK: todo")

    def test_history_and_errors(self):
        r = vault_root("m14hist", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo", html="<!doctype html><title>v1</title>\n")
        r.text("edit_file", path="vault/todo/index.html", old="v1", new="v2")
        r.text("write_file", path="vault/todo/app.js", content="1\n")
        lines = r.text("app_rollback", app="todo", steps="0").splitlines()
        self.assertEqual(lines[0], "todo: 2 changes")
        self.assertRegex(lines[1], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\S* write_file app\.js \(new\)$")
        self.assertRegex(lines[2], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\S* edit_file index\.html \(33 bytes\)$")
        self.assertEqual((r.vault / "todo" / "index.html").read_text(encoding="utf-8"), "<!doctype html><title>v2</title>\n", "history changes nothing")
        res = r.tool("app_rollback", app="nope")
        self.assertEqual((res.get("execution") or {}).get("state"), "invalid_input", res)
        r.set_vault(None)
        res = r.tool("app_rollback", app="todo")
        self.assertEqual((res.get("execution") or {}).get("state"), "refused", res)
        self.assertEqual(res["result"], "REFUSED: no apps folder chosen yet (Apps ▸ Choose apps folder…)")


class PruneTests(unittest.TestCase):
    """M14-B3"""

    @staticmethod
    def _entries(count, start, step):
        out = []
        for i in range(count):
            at = start + step * i
            out.append({"at": at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "file": "index.html", "bytes": 10,
                        "stored": at.strftime("%Y%m%dT%H%M%S%fZ") + "__index.html", "reason": "edit_file"})
        return out

    def test_prune_plan_keeps_fifty_plus_one_per_day_for_thirty_days(self):
        """The newest 50 stay; for each earlier UTC day of the last 30 that the 50 do not cover, its newest
        entry stays; nothing older than 30 days stays."""
        vault = vault_module()
        now = dt.datetime(2026, 10, 19, 12, 0, 0)
        # 120 entries, one every 10 minutes back to 2026-10-18 16:10, then 10 a day for the 40 days before.
        recent = self._entries(120, now - dt.timedelta(minutes=10 * 119), dt.timedelta(minutes=10))
        older = []
        for day in range(1, 41):
            base = now - dt.timedelta(days=day, hours=1)
            older += self._entries(10, base - dt.timedelta(hours=9), dt.timedelta(hours=1))
        entries = sorted(older + recent, key=lambda e: e["at"])
        kept = [e["stored"] for e in vault.prune_plan(entries, now)]
        self.assertEqual(kept, sorted(kept), "original order")
        newest = [e["stored"] for e in entries[-50:]]
        self.assertEqual(kept[-50:], newest, "the newest 50 stay")
        self.assertTrue(all(e["at"].startswith("2026-10-19") for e in entries[-50:]), "fixture: the 50 cover only today")
        rest = entries[:-50]
        by_day = {}
        for e in rest:
            by_day[e["at"][:10]] = e["stored"]  # sorted, so the last one seen is that day's newest
        cutoff = (now.date() - dt.timedelta(days=30)).isoformat()
        expected_days = sorted(stored for day, stored in by_day.items() if day >= cutoff and day != "2026-10-19")
        self.assertEqual(kept[:-50], expected_days)
        self.assertEqual(len(kept[:-50]), 30, "2026-10-18 back to 2026-09-19: one each")
        self.assertIn(max(e["stored"] for e in recent if e["at"].startswith("2026-10-18")), kept,
                      "2026-10-18's newest is one of the 10-minute entries, not a day-1 entry")
        self.assertFalse(any(stored.startswith("202609") and stored[:8] < "20260919" for stored in kept), "nothing older than 30 days")
        self.assertEqual(vault.prune_plan(entries[:40], now), entries[:40], "50 or fewer: everything stays")

    def test_prune_runs_after_each_snapshot(self):
        r = vault_root("m14prune", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo", html="0\n")
        for i in range(1, 56):
            r.text("write_file", path="vault/todo/index.html", content="%d\n" % i)
        entries = r.snapshots("todo")
        self.assertEqual(len(entries), 50)
        store = r.vault / ".iter" / "snapshots" / "todo"
        files = sorted(p.name for p in store.iterdir() if p.name != "log.jsonl")
        self.assertEqual(files, sorted(e["stored"] for e in entries), "files and lines pruned together")
        self.assertEqual((store / entries[0]["stored"]).read_text(encoding="utf-8"), "5\n")


@unittest.skipUnless(NODE, "needs node")
class UndoMenuTests(unittest.TestCase):
    """M14-B4"""

    def test_undo_item_for_the_displayed_vault_app_with_history(self):
        require_m14()
        catalog = [{"id": "todo", "kind": "vault", "path": "/v/todo", "entry": "index.html", "brief": None}]
        items = menu_template(catalog, {"vault": "/v", "recentVaults": [], "undoable": ["todo"]})
        undo = next(i for i in items if (i.get("label") or "").startswith("Undo"))
        self.assertEqual((undo["label"], undo["click"]), ("Undo Iter's last change to todo", "undo:todo"))
        items = menu_template(catalog, {"vault": "/v", "recentVaults": [], "undoable": []})
        self.assertFalse(any((i.get("label") or "").startswith("Undo") for i in items), "no history, no item")
        main = main_js()
        self.assertIn("'rollback'", main)
        self.assertIn("[vault] rolled back", main)


if __name__ == "__main__":
    unittest.main()
