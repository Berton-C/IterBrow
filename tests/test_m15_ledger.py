#!/usr/bin/env python3
"""M15-C2..C6: the build ledger — facts from the ask (literal), the contract check (observed) and probes;
conclusions by MeTTa rules in the real Hyperon at observation time; the ledger rendered into tool results
and read from atoms by build_mode; the catalog drops what is gone; NACE learns through the courier's queue.

Spec: docs/milestones/M15_build_ledger.md section C. The check itself (page script) is tested in
tests/test_m15_check.py; here its results are dicts of the shape it returns.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m15_support import (pending, require_m15, ledger, seed_units, run_metta, hyperon_available, briefs,  # noqa: E402
                         VaultRoot, ITER_SRC, SEED)

TODO_ASK = next(b["ask"] for b in briefs() if b["id"] == "todo")
NOTES_ASK = next(b["ask"] for b in briefs() if b["id"] == "notes")

# What checkScript returns for tests/fixtures/m15/todo_unguarded.html with the todo ask's selectors.
TODO_CHECK = {
    "selectors": {"#new-todo": {"present": True, "visible": True}, "#add": {"present": True, "visible": True},
                  "#list": {"present": True, "visible": True}, ".label": {"present": False, "visible": False},
                  ".toggle": {"present": False, "visible": False}, ".delete": {"present": False, "visible": False}},
    "ready": True, "storage": {"prefixed": 0, "other": ["todos"]}, "scripts": ["cdn.example.com"],
    "forms": [{"selector": "#todo-form", "guarded": False}], "placeholder": False, "title": "Todo",
}
NOTES_CHECK = {
    "selectors": {"#note-body": {"present": True, "visible": True}, "#save": {"present": True, "visible": True},
                  "#notes": {"present": True, "visible": True}, "#preview": {"present": True, "visible": True}},
    "ready": True, "storage": {"prefixed": 1, "other": []}, "scripts": [], "forms": [], "placeholder": False, "title": "Notes",
}
NOTES_PROBE_JSON = {"steps": [{"kind": "fill", "selector": "#note-body", "value": "# Hello\n*text*"}, {"kind": "click", "selector": "#save"}],
                    "assertions": [{"kind": "count", "selector": "#notes li", "expected": 1},
                                   {"kind": "text", "selector": "#preview h1", "expected": "Hello"}]}


def atoms_of(facts):
    """{key: atom} from the extractors' [(key, atom)] (or dict)."""
    return dict(facts) if not isinstance(facts, dict) else facts


def probe_result(passed, failed, observations):
    return {"passed": passed, "failed": failed, "observations": observations}


class AskFactsTests(unittest.TestCase):
    """M15-C2 (ask): literal selectors and persist, nothing else."""

    def test_only_what_the_ask_names(self):
        facts = atoms_of(ledger().facts_from_ask("todo", TODO_ASK))
        atoms = set(facts.values())
        for sel in ("#new-todo", "#add", "#list", ".label", ".toggle", ".delete"):
            self.assertIn('(ask-requires todo "%s")' % sel, atoms)
        self.assertIn("(ask-requires todo persist)", atoms)
        self.assertEqual(len(atoms), 7, "no inferred requirements: %s" % sorted(atoms))
        self.assertTrue(all(k.startswith("state:build:todo:ask:") for k in facts))
        loose = atoms_of(ledger().facts_from_ask("x", "Make me something nice that remembers what I typed."))
        self.assertEqual(set(loose.values()), {"(ask-requires x persist)"}, "a loose ask yields fewer requirements, never wrong ones")


class CheckFactsTests(unittest.TestCase):
    """M15-C2 (check): the observed page becomes atoms, one family, replaced wholesale."""

    def test_the_unguarded_todo_and_the_built_notes(self):
        facts = atoms_of(ledger().facts_from_check("todo", TODO_CHECK))
        atoms = set(facts.values())
        self.assertIn('(app-has todo "#add")', atoms)
        self.assertIn('(app-visible todo "#add")', atoms)
        self.assertNotIn('(app-has todo ".delete")', atoms)
        self.assertIn("(app-ready todo true)", atoms)
        self.assertIn("(app-stores todo other)", atoms)
        self.assertIn('(app-script todo external "cdn.example.com")', atoms)
        self.assertIn('(app-form todo "#todo-form" unguarded)', atoms)
        self.assertIn("(app-placeholder todo gone)", atoms)
        self.assertTrue(all(k.startswith("state:build:todo:check:") for k in facts))
        notes = set(atoms_of(ledger().facts_from_check("notes", NOTES_CHECK)).values())
        self.assertIn("(app-stores notes prefixed)", notes)
        self.assertFalse(any("app-form" in a or "app-script" in a for a in notes))

    def test_a_hidden_element_is_present_not_visible(self):
        check = dict(TODO_CHECK, selectors={"#add": {"present": True, "visible": False}})
        atoms = set(atoms_of(ledger().facts_from_check("todo", check)).values())
        self.assertIn('(app-has todo "#add")', atoms)
        self.assertNotIn('(app-visible todo "#add")', atoms)


class ProbeFactsTests(unittest.TestCase):
    """M15-C2 (probe): runs, assertions and what the probe covers."""

    def test_probe_result_becomes_atoms(self):
        result = probe_result(2, 1, [{"kind": "count", "selector": "#list li", "actual": 2, "expected": 3, "passed": False},
                                     {"kind": "text", "selector": "#title", "actual": "Todo", "expected": "Todo", "passed": True},
                                     {"kind": "value", "selector": "#new-todo", "actual": "", "expected": "", "passed": True}])
        probe_json = {"steps": [{"kind": "fill", "selector": "#new-todo", "value": "milk"}, {"kind": "click", "selector": "#add"}],
                      "assertions": [{"kind": "count", "selector": "#list li", "expected": 3}]}
        facts = atoms_of(ledger().facts_from_probe("todo", result, probe_json, seq=7))
        atoms = set(facts.values())
        self.assertIn("(probe-run todo 7 2 1)", atoms)
        self.assertIn('(probe-assertion todo 7 "count #list li" failed "2≠3")', atoms)
        self.assertIn('(probe-assertion todo 7 "text #title" passed "")', atoms)
        for sel in ("#new-todo", "#add", "#list"):
            self.assertIn('(probe-covers todo 7 "%s")' % sel, atoms, "steps and assertions cover the selectors they touch")
        self.assertTrue(all(k.startswith("state:build:todo:probe:") for k in facts))


@unittest.skipUnless(hyperon_available(), "needs hyperon")
class RulesTests(unittest.TestCase):
    """M15-C3: the rules in seeds/build_ledger.metta, in the real engine, through the one-shot worker."""

    def _conclude(self, app, atoms):
        return ledger().conclude(app, lambda code: run_metta(seed_units(), atoms, code))

    def test_missing_unproven_contract_and_next(self):
        module = ledger()
        atoms = {}
        atoms.update(atoms_of(module.facts_from_ask("todo", TODO_ASK)))
        atoms.update(atoms_of(module.facts_from_check("todo", TODO_CHECK)))
        atoms["state:build:todo:open:1"] = "(app-opened todo 1)"
        c = self._conclude("todo", atoms)
        self.assertEqual(sorted(c["missing"]), [".delete", ".label", ".toggle"], "asked and not present")
        self.assertEqual(c["hidden"], [])
        self.assertEqual(sorted(c["unproven"]), ["#add", "#list", "#new-todo"], "present, no probe since the open")
        self.assertEqual(sorted(c["contract"]), sorted(['form "#todo-form"', "storage", 'script "cdn.example.com"']))
        self.assertEqual(c["next"], "build")
        self.assertEqual(c["regressed"], [])

    def test_hidden_is_its_own_verdict(self):
        module = ledger()
        atoms = atoms_of(module.facts_from_ask("todo", "A todo with #add and #list."))
        check = dict(TODO_CHECK, selectors={"#add": {"present": True, "visible": False}, "#list": {"present": True, "visible": True}},
                     storage={"prefixed": 1, "other": []}, scripts=[], forms=[])
        atoms.update(atoms_of(module.facts_from_check("todo", check)))
        c = self._conclude("todo", atoms)
        self.assertEqual(c["missing"], [])
        self.assertEqual(c["hidden"], ["#add"])
        self.assertEqual(c["next"], "build")

    def test_probe_then_report_then_regression(self):
        module = ledger()
        atoms = {}
        atoms.update(atoms_of(module.facts_from_ask("notes", NOTES_ASK)))
        atoms.update(atoms_of(module.facts_from_check("notes", NOTES_CHECK)))
        atoms["state:build:notes:open:2"] = "(app-opened notes 2)"
        c = self._conclude("notes", atoms)
        self.assertEqual(c["missing"], [])
        self.assertEqual(c["contract"], [])
        self.assertTrue(c["unproven"])
        self.assertEqual(c["next"], "probe")
        ok = probe_result(2, 0, [{"kind": "count", "selector": "#notes li", "actual": 1, "expected": 1, "passed": True},
                                 {"kind": "text", "selector": "#preview h1", "actual": "Hello", "expected": "Hello", "passed": True}])
        atoms.update(atoms_of(module.facts_from_probe("notes", ok, NOTES_PROBE_JSON, seq=3)))
        c = self._conclude("notes", atoms)
        self.assertEqual(c["unproven"], [], "every asked selector is covered by a passing run since the open")
        self.assertEqual(c["probe"], {"passed": 2, "failed": 0, "failures": []})
        self.assertEqual(c["next"], "report")
        # A re-open after an edit: unproven again (the probe predates it); a later probe failing what passed: regressed.
        atoms["state:build:notes:open:4"] = "(app-opened notes 4)"
        self.assertTrue(self._conclude("notes", atoms)["unproven"])
        bad = probe_result(1, 1, [{"kind": "count", "selector": "#notes li", "actual": 1, "expected": 1, "passed": True},
                                  {"kind": "text", "selector": "#preview h1", "actual": "", "expected": "Hello", "passed": False}])
        atoms.update(atoms_of(module.facts_from_probe("notes", bad, NOTES_PROBE_JSON, seq=5)))
        c = self._conclude("notes", atoms)
        self.assertEqual(c["regressed"], ["text #preview h1"])
        self.assertEqual(c["next"], "build")

    def test_the_seed_is_declared(self):
        manifest = json.loads((ITER_SRC / "state_manifest.json").read_text(encoding="utf-8"))
        entry = next((e for e in manifest["entries"] if e["path"] == "seeds/build_ledger.metta"), None)
        self.assertIsNotNone(entry)
        self.assertEqual((entry["role"], entry["format"]), ("source_seed", "metta"))
        self.assertTrue(SEED.is_file())


class RenderTests(unittest.TestCase):
    """M15-C4 (render)"""

    def test_render_is_short_and_says_next(self):
        render = ledger().render
        text = render("todo", {"missing": [".delete", ".toggle"], "hidden": ["#add"], "unproven": ["#list"], "regressed": [],
                               "contract": ['form "#todo-form"', "storage"],
                               "probe": {"passed": 2, "failed": 1, "failures": ["count #list li: 2≠3"]}, "next": "build"})
        self.assertTrue(text.startswith("[build ledger todo]"))
        self.assertIn("missing (from the ask's named ids): .delete, .toggle", text)
        self.assertIn("hidden: #add", text)
        self.assertIn("unproven: #list", text)
        self.assertIn('contract: form "#todo-form" unguarded, storage other', text)
        self.assertIn("probe: 2 passed, 1 failed (count #list li: 2≠3)", text)
        self.assertTrue(text.rstrip().endswith("next: build]"))
        self.assertLessEqual(len(text.splitlines()), 8)
        clean = render("notes", {"missing": [], "hidden": [], "unproven": [], "regressed": [], "contract": [],
                                 "probe": {"passed": 4, "failed": 0, "failures": []}, "next": "report"})
        self.assertIn("probe: 4 passed, 0 failed", clean)
        self.assertIn("next: report", clean)
        self.assertNotIn("missing", clean)
        self.assertIn("unproven", render("x", {"missing": [], "hidden": [], "unproven": ["#a"], "regressed": [], "contract": [], "probe": None, "next": "probe"}))


class RecordedWhereFactsAriseTests(unittest.TestCase):
    """M15-C2 / C4 / C5: the observing tools record and carry the ledger; the file tools only remind;
    build_mode reads atoms; the catalog drops what is gone."""

    def test_who_records_who_reminds_who_reads(self):
        require_m15()
        tools = ITER_SRC / "tools"
        for name in ("browser_open_app", "app_probe"):
            src = (tools / (name + ".py")).read_text(encoding="utf-8")
            self.assertIn("build_ledger", src, name)
            self.assertIn("· ledger:", src, name)
            self.assertIn("not recorded", src, "%s: the line comes from the observation even if the store write fails" % name)
            self.assertRegex(src, r"except Exception", "%s: a ledger failure never fails the tool" % name)
        probe = (tools / "app_probe.py").read_text(encoding="utf-8")
        self.assertIn("facts_from_probe", probe)
        self.assertIn("facts_from_check", (tools / "browser_open_app.py").read_text(encoding="utf-8"))
        for name in ("write_file", "edit_file"):
            src = (tools / (name + ".py")).read_text(encoding="utf-8")
            self.assertIn("changed since last check", src, name)
            self.assertNotIn("facts_from", src, "%s: the file tools observe nothing" % name)
        mode = (ITER_SRC / "transformations" / "build_mode.py").read_text(encoding="utf-8")
        self.assertIn("facts_from_ask", mode)
        self.assertIn("[build ledger", mode)
        self.assertIn("stale", mode)
        self.assertNotIn("query(", mode, "build_mode reads atoms; it never runs a MeTTa query per cycle")
        apps = (ITER_SRC / "iterbrow_runtime" / "local_apps.py").read_text(encoding="utf-8")
        self.assertIn("state:build:", apps, "the catalog drops the facts of apps that are gone")
        self.assertIn("state:build:", (tools / "new_app.py").read_text(encoding="utf-8"))

    def test_write_file_in_a_vault_app_reminds_and_nothing_else(self):
        r = VaultRoot("m15remind", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo", html="<!doctype html>")
        out = r.text("write_file", path="vault/todo/index.html", content="<!doctype html><title>Todo</title>")
        self.assertTrue(out.startswith("WROTE vault/todo/index.html ("), out)
        self.assertIn("· ledger: changed since last check", out)
        self.assertIn("browser_open_app", out)
        plain = r.text("write_file", path="scratch/x.txt", content="x")
        self.assertNotIn("ledger", plain, "outside a vault app, nothing")


class NaceLearnsTests(unittest.TestCase):
    """M15-C6"""

    def test_patterns_queue_through_the_courier_like_idle_cycle_detector(self):
        require_m15()
        src = (ITER_SRC / "iterbrow_runtime" / "build_ledger.py").read_text(encoding="utf-8")
        self.assertIn("nace_pending.metta", src)
        self.assertIn("(pending-revision pattern probe_before_report", src)
        self.assertIn("(pending-revision pattern edit_keeps_passing", src)
        self.assertIn("def queue_pattern(", src)
        for name in ("nace_courier.py", "tool_reliability_tracker.py"):
            diff = subprocess.run(["git", "diff", "--stat", "eea6737", "--", "iter/transformations/" + name],
                                  cwd=str(ITER_SRC.parent), capture_output=True, text=True)
            self.assertEqual(diff.stdout.strip(), "", name + " untouched")


if __name__ == "__main__":
    unittest.main()
