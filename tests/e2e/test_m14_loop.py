#!/usr/bin/env python3
"""M14-D/E2E and M14-F3: the foundry loop through the real loop (fake model, no Electron): build mode shows
the loop, new_app scaffolds into the vault, a change without a probe draws the build_watch note on the next
request, app_probe fails for the honest reason (no bridge), app_rollback restores the file; and every
transformation of a cycle runs in one process.

Spec: docs/milestones/M14_vault_and_foundry_loop.md sections D and F.
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from harness import IterRun, send, tool  # noqa: E402
from m14_support import pending, require_m14  # noqa: E402

PID_TRANSFORMATION = """import os
DESCRIPTION = "M14 e2e: records the pid each transformation batch runs in."
def transform(messages, tools):
    with open(os.path.join(os.environ.get("ITER_DIR", "."), "m14_pids.txt"), "a") as handle:
        handle.write("%d\\n" % os.getpid())
    return messages, tools
"""


class FoundryLoopTests(unittest.TestCase):
    @pending("M14-D1")
    def test_build_mode_scaffold_note_probe_rollback(self):
        require_m14()
        script = [
            [tool("new_app", id="todo", title="Todo")],
            [tool("write_file", path="vault/todo/README.md", content="changed by the loop\n")],
            [send("Working on it")],  # a message with a change and no probe since: the note follows
            [tool("app_probe", app="todo")],
            [tool("app_rollback", app="todo")],
            [send("M14-DONE")],
        ]
        run = IterRun(script, name="m14")
        vault = run.work / "vault"
        vault.mkdir()
        (run.root / ".runtime" / "settings.json").write_text(json.dumps({"vault": str(vault)}), encoding="utf-8")
        with run:
            run.say("build me a todo app in the vault")
            run.wait_for_reply("M14-DONE", timeout=600)
            run.stop()
            results = [m["content"] for m in run.experience() if m.get("role") == "tool"]
            self.assertTrue(any("NEW-APP vault/todo: index.html, probe.json, README.md" in c for c in results), results)
            self.assertTrue(any("WROTE vault/todo/README.md" in c for c in results), results)
            probe = next(c for c in results if "PROBE" in c or "bridge" in c.lower() or "not running" in c.lower())
            self.assertIn("not running", probe, "the probe failed for the real reason: no bridge in this harness")
            self.assertTrue(any(re.search(r"ROLLED BACK todo: README\.md \(to ", c) for c in results), results)
            self.assertEqual((vault / "todo" / "README.md").read_text(encoding="utf-8").count("changed by the loop"), 0, "restored")
            self.assertTrue((vault / "todo" / "index.html").is_file())
            requests = run.requests()
            self.assertTrue(any("Research" in r["system"] and "Report" in r["system"] and "never a progress note" in r["system"]
                                for r in requests), "build mode put the loop in the prompt")
            noted = [i for i, r in enumerate(requests) if "[build: vault/todo changed since its last probe" in r["system"]]
            self.assertTrue(noted, "the note appeared after the send that followed the change")
            self.assertFalse(any("[build: vault/todo changed" in r["system"] for r in requests[:3]), "not before the send")

    @pending("M14-F3")
    def test_one_process_per_cycle_for_the_transformations(self):
        require_m14()
        run = IterRun([[send("first")], [send("second")], [send("M14-F3-DONE")]], name="m14f3")
        (run.root / "transformations" / "zz_m14_pid.py").write_text(PID_TRANSFORMATION, encoding="utf-8")
        with run:
            run.say("hello")
            run.wait_for_reply("M14-F3-DONE", timeout=600)
            run.stop()
            # F3: one process per cycle for the transformations.
            pids = (run.root / "m14_pids.txt").read_text(encoding="utf-8").split()
            self.assertGreaterEqual(len(pids), 3)
            prep = [json.loads(line[line.index("{"):]) for line in run.read_log("iter.log").splitlines() if "[request preparation]" in line]
            self.assertTrue(prep, "the preparation line is logged")
            self.assertTrue(all(p.get("transformations_processes") == 1 for p in prep), prep)
            self.assertGreaterEqual(len(set(pids)), 3, "a fresh worker per cycle (never one long-lived process)")
            self.assertTrue(all(p["transformations_seconds"].get("zz_m14_pid.py") is not None for p in prep), "timings keep one entry per transformation")


if __name__ == "__main__":
    unittest.main()
