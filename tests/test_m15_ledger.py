#!/usr/bin/env python3
"""M15-C1..C5: the build ledger — facts from asks, files and probes as atoms; conclusions by MeTTa rules in
the real Hyperon; the ledger rendered into the prompt and the file tools' results; NACE learns through the
courier's queue.

Spec: docs/milestones/M15_build_ledger.md section C. Fixtures: tests/fixtures/m15/ (notes_built.html is the
notes app Iter built on 2026-10-20; todo_scaffold.html a bare new_app scaffold; todo_unguarded.html a hand-made
app with the mistakes the probes found: a form that submits, storage outside iter:<id>:, an external script).
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m15_support import (pending, require_m15, ledger, seed_units, run_metta, hyperon_available, fixture, briefs,  # noqa: E402
                         VaultRoot, transformation, assistant, tool_result, user, system, ITER_SRC, SEED)
from m14_support import fake_bridge  # noqa: E402

TODO_ASK = next(b["ask"] for b in briefs() if b["id"] == "todo")


def atoms_of(facts):
    """{key: atom} from the extractors' [(key, atom)] (or dict)."""
    return dict(facts) if not isinstance(facts, dict) else facts


class AskFactsTests(unittest.TestCase):
    """M15-C1 (asks)"""

    @pending("M15-C1")
    def test_selectors_and_requirements_from_the_todo_brief(self):
        atoms = atoms_of(ledger().facts_from_ask("todo", TODO_ASK))
        values = set(atoms.values())
        for sel in ("#new-todo", "#add", "#list", ".label", ".toggle", ".delete"):
            self.assertIn('(ask-requires todo "%s")' % sel, values, sel)
        self.assertIn("(ask-requires todo persist)", values, "'persist across a reload'")
        self.assertTrue(all(k.startswith("state:build:todo:ask:") for k in atoms), list(atoms)[:3])
        self.assertEqual(atoms_of(ledger().facts_from_ask("x", "hello there")), {}, "an ask with no selectors is no facts")
        dark = atoms_of(ledger().facts_from_ask("todo", "Add a dark mode toggle to todo: a #theme-toggle button that switches light/dark and remembers the choice across reloads."))
        self.assertIn('(ask-requires todo "#theme-toggle")', set(dark.values()))
        self.assertIn("(ask-requires todo persist)", set(dark.values()))


class HtmlFactsTests(unittest.TestCase):
    """M15-C1 (files)"""

    @pending("M15-C1")
    def test_the_notes_app_iter_built(self):
        values = set(atoms_of(ledger().facts_from_html("notes", fixture("notes_built.html"))).values())
        for sel in ("#title", "#theme-toggle", "#note-body", "#save", "#preview", "#notes"):
            self.assertIn('(app-has notes "%s")' % sel, values, sel)
        self.assertIn('(app-listens notes "#save" click)', values)
        self.assertIn('(app-stores notes "iter:notes:")', values)
        self.assertIn("(app-ready-flag notes true)", values)
        self.assertIn("(app-placeholder notes gone)", values)
        self.assertFalse(any("app-form-submit" in v for v in values))
        self.assertFalse(any("app-script" in v for v in values), "no external scripts")

    @pending("M15-C1")
    def test_the_bare_scaffold_and_the_unguarded_app(self):
        scaffold = set(atoms_of(ledger().facts_from_html("todo", fixture("todo_scaffold.html"))).values())
        self.assertIn("(app-placeholder todo present)", scaffold)
        self.assertIn('(app-has todo "#title")', scaffold)
        self.assertIn("(app-ready-flag todo true)", scaffold, "the scaffold sets the flag in init()")
        bad = set(atoms_of(ledger().facts_from_html("todo", fixture("todo_unguarded.html"))).values())
        self.assertIn('(app-form-submit todo "#todo-form" unguarded)', bad)
        self.assertIn("(app-stores todo other)", bad, "localStorage keys outside iter:todo:")
        self.assertIn('(app-script todo external "cdn.example.com")', bad)
        self.assertIn('(app-has todo ".toggle")', bad)
        self.assertIn('(app-has todo ".label")', bad)
        self.assertIn('(app-listens todo "#todo-form" submit)', bad)
        self.assertFalse(any('(app-listens todo "#add"' in v for v in bad), "#add has no listener of its own")


class ProbeFactsTests(unittest.TestCase):
    """M15-C1 (probes)"""

    @pending("M15-C1")
    def test_probe_result_text_becomes_atoms(self):
        text = ("Step 12:00: [NACE advisory x] PROBE todo (probe.json): 2 passed, 1 failed\n"
                "✓ text #title: expected 'Todo' got 'Todo'\n✓ visible #add: expected true got true\n"
                "✗ count #list li: expected 3 got 2\nready=true")
        atoms = atoms_of(ledger().facts_from_probe("todo", text, seq=7))
        values = set(atoms.values())
        self.assertIn("(probe-run todo 7 2 1)", values)
        self.assertIn('(probe-assertion todo 7 "count #list li" failed "2≠3")', values)
        self.assertIn('(probe-assertion todo 7 "text #title" passed)', values)
        self.assertEqual(atoms_of(ledger().facts_from_probe("todo", "ERROR: no assertions given", seq=8)), {}, "a probe that did not run is no fact")


@unittest.skipUnless(hyperon_available(), "needs hyperon")
class RulesTests(unittest.TestCase):
    """M15-C3: the rules in seeds/build_ledger.metta, in the real engine."""

    def _conclude(self, app, atoms):
        module = ledger()
        return module.conclude(app, lambda code: run_metta(seed_units(), atoms, code))

    @pending("M15-C3")
    def test_missing_unwired_unproven_contract_and_next(self):
        module = ledger()
        atoms = {}
        atoms.update(atoms_of(module.facts_from_ask("todo", TODO_ASK)))
        atoms.update(atoms_of(module.facts_from_html("todo", fixture("todo_unguarded.html"))))
        atoms["state:build:todo:seq"] = "(app-file-seq todo 3)"
        c = self._conclude("todo", atoms)
        self.assertEqual(sorted(c["missing"]), [".delete"], "everything else the ask names is present")
        self.assertIn("#add", c["unwired"], "named as an action, present, no listener")
        self.assertTrue(c["unproven"], "no probe since the file")
        self.assertEqual(sorted(c["contract"]), sorted(["storage", 'form-submit "#todo-form"', 'script "cdn.example.com"']))
        self.assertEqual(c["next"], "build")
        self.assertEqual(c["regressed"], [])

    @pending("M15-C3")
    def test_probe_then_report(self):
        module = ledger()
        atoms = {}
        atoms.update(atoms_of(module.facts_from_ask("notes", next(b["ask"] for b in briefs() if b["id"] == "notes"))))
        atoms.update(atoms_of(module.facts_from_html("notes", fixture("notes_built.html"))))
        atoms["state:build:notes:seq"] = "(app-file-seq notes 2)"
        c = self._conclude("notes", atoms)
        self.assertEqual(c["missing"], [])
        self.assertEqual(c["contract"], [])
        self.assertTrue(c["unproven"])
        self.assertEqual(c["next"], "probe")
        probe = "PROBE notes (probe.json): 4 passed, 0 failed\n✓ count #notes li: expected 1 got 1\n✓ text #preview h1: expected 'Hello' got 'Hello'\n✓ text #preview em: expected 'text' got 'text'\n✓ count #preview li: expected 2 got 2"
        atoms.update(atoms_of(module.facts_from_probe("notes", probe, seq=3)))
        c = self._conclude("notes", atoms)
        self.assertFalse(c["unproven"])
        self.assertEqual(c["probe"], {"passed": 4, "failed": 0, "failures": []})
        self.assertEqual(c["next"], "report")
        # An edit after the probe: unproven again; a later probe that fails what passed: regressed.
        atoms["state:build:notes:seq"] = "(app-file-seq notes 4)"
        self.assertTrue(self._conclude("notes", atoms)["unproven"])
        atoms.update(atoms_of(module.facts_from_probe("notes", "PROBE notes (probe.json): 3 passed, 1 failed\n✗ count #preview li: expected 2 got 0", seq=5)))
        c = self._conclude("notes", atoms)
        self.assertEqual(c["regressed"], ["count #preview li"])
        self.assertEqual(c["next"], "build")

    @pending("M15-C3")
    def test_the_seed_is_declared(self):
        manifest = json.loads((ITER_SRC / "state_manifest.json").read_text(encoding="utf-8"))
        entry = next((e for e in manifest["entries"] if e["path"] == "seeds/build_ledger.metta"), None)
        self.assertIsNotNone(entry)
        self.assertEqual((entry["role"], entry["format"]), ("source_seed", "metta"))
        self.assertTrue(SEED.is_file())


class RenderTests(unittest.TestCase):
    """M15-C4 (render)"""

    @pending("M15-C4")
    def test_render_is_short_and_says_next(self):
        render = ledger().render
        text = render("todo", {"missing": [".delete", "#theme-toggle"], "unwired": ["#add"], "unproven": False,
                               "regressed": [], "contract": ['form-submit "#todo-form"'],
                               "probe": {"passed": 2, "failed": 1, "failures": ["count #list li: 2≠3"]}, "next": "build"})
        self.assertTrue(text.startswith("[build ledger todo]"))
        self.assertIn("missing: .delete, #theme-toggle", text)
        self.assertIn("unwired: #add", text)
        self.assertIn('contract: form-submit "#todo-form"', text)
        self.assertIn("probe: 2 passed, 1 failed (count #list li: 2≠3)", text)
        self.assertTrue(text.rstrip().endswith("next: build]"))
        self.assertLessEqual(len(text.splitlines()), 8)
        clean = render("notes", {"missing": [], "unwired": [], "unproven": False, "regressed": [], "contract": [],
                                 "probe": {"passed": 4, "failed": 0, "failures": []}, "next": "report"})
        self.assertIn("probe: 4 passed, 0 failed", clean)
        self.assertIn("next: report", clean)
        self.assertNotIn("missing", clean)
        self.assertIn("unproven", render("x", {"missing": [], "unwired": [], "unproven": True, "regressed": [], "contract": [], "probe": None, "next": "probe"}))


class RecordedWhereFactsAriseTests(unittest.TestCase):
    """M15-C2 / C4: the tools record facts and carry the ledger line; build_mode renders it."""

    @pending("M15-C2")
    def test_file_tools_and_app_probe_record_and_report(self):
        require_m15()
        for name in ("write_file", "edit_file", "new_app", "app_probe"):
            src = (ITER_SRC / "tools" / (name + ".py")).read_text(encoding="utf-8")
            self.assertIn("build_ledger", src, name)
        for name in ("write_file", "edit_file", "new_app"):
            src = (ITER_SRC / "tools" / (name + ".py")).read_text(encoding="utf-8")
            self.assertIn("· ledger:", src, name)
        mode = (ITER_SRC / "transformations" / "build_mode.py").read_text(encoding="utf-8")
        self.assertIn("build_ledger", mode)
        self.assertIn("[build ledger", mode)
        self.assertIn("facts_from_ask", mode)
        probe = (ITER_SRC / "tools" / "app_probe.py").read_text(encoding="utf-8")
        self.assertIn("facts_from_probe", probe)
        for name in ("write_file", "edit_file", "new_app", "app_probe"):
            src = (ITER_SRC / "tools" / (name + ".py")).read_text(encoding="utf-8")
            self.assertRegex(src, r"except Exception", "%s: a ledger failure never fails the tool" % name)

    @pending("M15-C4")
    def test_write_file_result_carries_the_ledger_line_in_a_vault_app(self):
        """A write to vault/todo/index.html answers with its ledger (the AtomSpace is the e2e harness's; here a
        throwaway ITER_DIR with no service: the line says what the extractors alone can say)."""
        r = VaultRoot("m15ledgerline", with_main_js=True)
        self.addCleanup(r.close)
        r.app("todo", html="<!doctype html>")
        out = r.text("write_file", path="vault/todo/index.html", content=fixture("todo_unguarded.html"))
        self.assertTrue(out.startswith("WROTE vault/todo/index.html ("), out)
        self.assertIn("· ledger:", out)
        self.assertIn("form-submit", out)
        self.assertIn("storage", out)
        plain = r.text("write_file", path="scratch/x.txt", content="x")
        self.assertNotIn("ledger", plain, "outside a vault app, nothing")


class NaceLearnsTests(unittest.TestCase):
    """M15-C5"""

    @pending("M15-C5")
    def test_patterns_queue_through_the_courier_like_idle_cycle_detector(self):
        require_m15()
        src = (ITER_SRC / "iterbrow_runtime" / "build_ledger.py").read_text(encoding="utf-8")
        self.assertIn("nace_pending.metta", src)
        self.assertIn("(pending-revision pattern probe_before_report", src)
        self.assertIn("(pending-revision pattern edit_keeps_passing", src)
        for name in ("nace_courier.py", "tool_reliability_tracker.py"):
            import subprocess
            diff = subprocess.run(["git", "diff", "--stat", "eea6737", "--", "iter/transformations/" + name],
                                  cwd=str(ITER_SRC.parent), capture_output=True, text=True)
            self.assertEqual(diff.stdout.strip(), "", name + " untouched")
        # The courier turns a `(pending-revision pattern <name> confirmed|disconfirmed)` line into a
        # pattern-efficacy belief the way it does for prioritize_user (idle_cycle_detector); nothing else is needed.
        self.assertIn("def queue_pattern(", src)


if __name__ == "__main__":
    unittest.main()
