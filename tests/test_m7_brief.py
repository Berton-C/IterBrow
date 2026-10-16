#!/usr/bin/env python3
"""M7-C1..C3: flourishing briefs — two lines per app, stored with the app, read into the prompt
when the feature is on, drift named as a card.

Spec: docs/milestones/M7_soul_personality.md section C.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m7_support import (pending, m7_root, require_m7, run_transformation, write_soul_settings,  # noqa: E402
                        ITER_SRC, FEATURES)

BLUEPRINT = {"title": "Little Orbit", "intention": "a calm planner", "invariants": ["no ads"], "acceptance": ["opens in 1s"]}


def make_project(root, app_id="orbit"):
    """A real Foundry project inside `root` (an ITER_DIR); returns its context hash."""
    import subprocess
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); from iterbrow_runtime.foundry_projects import FoundryProjects;"
            "p = FoundryProjects(sys.argv[1]); print(p.create(sys.argv[2], json.loads(sys.argv[3]))['source_context_hash'])")
    proc = subprocess.run([sys.executable, "-c", code, str(root), app_id, json.dumps(BLUEPRINT)],
                          env=dict(os.environ, ITER_DIR=str(root)), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip().splitlines()[-1]


def make_app_dir(root, name="crm"):
    (Path(root) / name).mkdir(exist_ok=True)
    (Path(root) / name / "index.html").write_text("<!doctype html><title>crm</title>")


class BriefToolTests(unittest.TestCase):
    """M7-C1"""

    def setUp(self):
        self.r = m7_root("m7brief")
        self.addCleanup(self.r.close)
        self.r.start()

    @pending("M7-C1")
    def test_brief_on_a_foundry_project_is_a_checkpointed_blueprint_change(self):
        write_soul_settings(self.r.root, "berton", {"brief": True})
        before = make_project(self.r.root)
        out = self.r.text("brief", app="orbit", for_whom="Bright, planning a week without dread",
                          flourishing="she closes it feeling lighter than when she opened it")
        self.assertEqual(out, "BRIEF-SAVED: orbit")
        blueprint = json.loads((Path(self.r.root) / "apps" / "orbit" / "blueprint.json").read_text())
        brief = blueprint["flourishing_brief"]
        self.assertEqual(brief["for"], "Bright, planning a week without dread")
        self.assertEqual(brief["flourishing"], "she closes it feeling lighter than when she opened it")
        self.assertEqual(brief["by"], "berton")
        self.assertIsInstance(brief["at"], int)
        for key in ("title", "intention", "invariants", "acceptance"):
            self.assertEqual(blueprint[key], BLUEPRINT[key], "the rest of the blueprint is untouched")
        history = sorted((Path(self.r.root) / "apps" / "orbit" / "history").glob("*.json"))
        self.assertEqual(len(history), 2, "the brief is a checkpoint (created + blueprint)")
        newest = max(history, key=lambda p: p.stat().st_mtime)
        record = json.loads(newest.read_text())
        self.assertEqual(record["operation"], "blueprint")
        self.assertEqual(record["provenance"], {"tool": "brief", "person": "berton"})
        self.assertNotEqual(record["source_context_hash"], before)
        self.assertEqual(self.r.text("brief", app="orbit"),
                         "orbit: for Bright, planning a week without dread. Flourishing: she closes it feeling lighter than when she opened it.")

    @pending("M7-C1")
    def test_brief_on_a_plain_app_dir_is_a_json_file(self):
        write_soul_settings(self.r.root, "berton", {"brief": True})
        make_app_dir(self.r.root, "crm")
        out = self.r.text("brief", app="crm", for_whom="Berton, keeping track of people he cares about",
                          flourishing="he remembers to reach out")
        self.assertEqual(out, "BRIEF-SAVED: crm")
        brief = json.loads((Path(self.r.root) / "crm" / "brief.json").read_text())
        self.assertEqual(sorted(brief), ["at", "by", "flourishing", "for"])
        self.assertEqual(self.r.text("brief", app="crm"), "crm: for Berton, keeping track of people he cares about. Flourishing: he remembers to reach out.")

    @pending("M7-C1")
    def test_read_without_a_brief_and_bad_calls(self):
        write_soul_settings(self.r.root, "berton", {"brief": True})
        make_app_dir(self.r.root, "music")
        self.assertEqual(self.r.text("brief", app="music"), "BRIEF-NONE: music")
        self.assertTrue(self.r.text("brief", app="nope", for_whom="x", flourishing="y").startswith("ERROR: no app named"))
        self.assertEqual(self.r.text("brief", app="music", for_whom="x"), "ERROR: give both lines or neither")
        self.assertTrue(self.r.text("brief", app="music", for_whom="x" * 201, flourishing="y").startswith("ERROR:"))
        self.assertTrue(self.r.text("brief", app="../etc", for_whom="x", flourishing="y").startswith("ERROR:"))
        self.assertFalse((Path(self.r.root) / "music" / "brief.json").exists())


class BriefPromptTests(unittest.TestCase):
    """M7-C2"""

    def setUp(self):
        self.r = m7_root("m7briefp")
        self.addCleanup(self.r.close)
        self.r.start()

    def _block(self, features):
        write_soul_settings(self.r.root, "berton", features)
        msgs, _ = run_transformation(self.r.root, "soul_brief.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        return msgs[-1]["content"]

    @pending("M7-C2")
    def test_briefs_block_lists_every_app_with_a_brief_sorted(self):
        make_project(self.r.root, "orbit")
        make_app_dir(self.r.root, "crm")
        make_app_dir(self.r.root, "music")  # no brief
        write_soul_settings(self.r.root, "berton", {"brief": True})
        self.r.text("brief", app="orbit", for_whom="Bright", flourishing="lighter")
        self.r.text("brief", app="crm", for_whom="Berton", flourishing="reaches out")
        content = self._block({"brief": True})
        self.assertEqual(content.count("## Briefs"), 1)
        block = content[content.index("## Briefs"):]
        self.assertEqual(block.strip().splitlines()[1:], ["crm: for Berton. Flourishing: reaches out.",
                                                          "orbit: for Bright. Flourishing: lighter."])
        self.assertNotIn("music", block)

    @pending("M7-C2")
    def test_feature_off_or_no_briefs_adds_nothing(self):
        make_app_dir(self.r.root, "crm")
        self.assertEqual(self._block({"brief": True}), "base", "no app has a brief")
        write_soul_settings(self.r.root, "berton", {"brief": True})
        self.r.text("brief", app="crm", for_whom="Berton", flourishing="reaches out")
        self.assertEqual(self._block({"brief": False}), "base", "feature off: no trace")
        self.assertEqual(self._block({f: False for f in FEATURES}), "base")


class DriftCardTests(unittest.TestCase):
    """M7-C3: drift is a brief card with continue / revise / drop; the presence block says so when brief is on."""

    @pending("M7-C3")
    def test_presence_describes_the_drift_card_when_brief_is_on(self):
        temp = tempfile.mkdtemp(prefix="m7drift-")
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        write_soul_settings(temp, "berton", {"brief": True})
        msgs, _ = run_transformation(temp, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})
        content = msgs[-1]["content"]
        for word in ("brief", "continue", "revise", "drop", "once"):
            self.assertIn(word, content, word)
        write_soul_settings(temp, "berton", {"brief": False, "forks": True})
        msgs, _ = run_transformation(temp, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})
        self.assertNotIn("revise", msgs[-1]["content"])

    @pending("M7-C3")
    def test_card_tool_accepts_the_drift_ids_for_kind_brief(self):
        r = m7_root("m7driftcard")
        self.addCleanup(r.close)
        r.start()
        out = r.text("card", kind="brief", title="This drifts from orbit's brief", body="It adds a streak counter; the brief says no dread.",
                     choices=[{"id": "continue", "label": "Continue anyway"}, {"id": "revise", "label": "Revise the brief"},
                              {"id": "drop", "label": "Drop the change"}])
        self.assertTrue(out.startswith("CARD-SENT: card-"), out)
        card_id = out.split()[1]
        choices = r.call("read_atoms", {"prefix": "state:soul_card_choice:%s:" % card_id})["atoms"]
        self.assertEqual(sorted(k.rsplit(":", 1)[1] for k in choices), ["continue", "drop", "revise"])


if __name__ == "__main__":
    unittest.main()
