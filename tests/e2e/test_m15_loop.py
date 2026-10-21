#!/usr/bin/env python3
"""M15-A (e2e) and M15-C (e2e): through the real loop with a fake model and the real AtomSpace —
a request over the target is degraded and still sent; one far over is announced once, never silent; and a
build's facts and ledger flow through the tools and the prompt.

Spec: docs/milestones/M15_build_ledger.md.
"""
import json
import re
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from harness import IterRun, send, tool, nop  # noqa: E402
from m15_support import pending, require_m15, fixture  # noqa: E402

PAD = """import os
DESCRIPTION = "M15 e2e: pads the system prompt by ITER_E2E_PAD characters (a stand-in for a bloated request)."
def transform(messages, tools):
    n = int(os.environ.get("ITER_E2E_PAD", "0") or 0)
    if n and messages and messages[0].get("role") == "system":
        messages[0]["content"] = messages[0]["content"] + "\\n" + ("pad " * (n // 4))
    return messages, tools
"""


def _prep_lines(run):
    return [json.loads(line[line.index("{"):]) for line in run.read_log("iter.log").splitlines() if "[request budget]" in line]


class BudgetLoopTests(unittest.TestCase):
    """M15-A2/A3 through the loop."""

    def _run(self, pad_chars, script, name):
        run = IterRun(script, name=name)
        (run.root / "transformations" / "aa_m15_pad.py").write_text(PAD, encoding="utf-8")
        import os
        os.environ["ITER_E2E_PAD"] = str(pad_chars)
        self.addCleanup(lambda: os.environ.pop("ITER_E2E_PAD", None))
        return run

    @pending("M15-A2")
    def test_over_the_target_the_request_is_degraded_and_still_sent(self):
        require_m15()
        # ≈ 15k estimated tokens of padding: over the target with every tool in, under it without the unprotected schemas.
        run = self._run(45000, [[send("M15-DEGRADED-OK")]], "m15deg")
        with run:
            run.say("hello")
            run.wait_for_reply("M15-DEGRADED-OK", timeout=600)
            run.stop()
            budgets = _prep_lines(run)
            self.assertTrue(budgets, "a request went out")
            self.assertTrue(any(b.get("degraded") for b in budgets), budgets[-1])
            self.assertFalse(any("I can't send this request" in r for r in run.replies()), "degraded, not blocked")
            self.assertTrue(all("calibration" in b for b in budgets))

    @pending("M15-A3")
    def test_far_over_the_target_the_block_is_announced_once(self):
        require_m15()
        run = self._run(400000, [[send("never")]], "m15blk")
        with run:
            run.say("hello")
            run.wait_for_log("[request blocked]", timeout=300)
            time.sleep(8)  # a second cycle would announce again if the notice were not once-only
            run.stop()
            notices = [r for r in run.replies() if "I can't send this request" in r]
            self.assertEqual(len(notices), 1, notices)
            self.assertRegex(notices[0], r"~[\d,]+ tokens over the 45,000")
            beat = json.loads((run.root / ".runtime" / "recovery" / "iter_heartbeat.json").read_text(encoding="utf-8"))
            self.assertEqual(beat.get("phase"), "request_blocked")


class LedgerLoopTests(unittest.TestCase):
    """M15-C2/C4 through the loop (real AtomSpace service, no browser)."""

    @pending("M15-C2")
    def test_facts_and_ledger_flow_through_tools_and_prompt(self):
        require_m15()
        script = [
            [tool("new_app", id="todo", title="Todo")],
            [tool("write_file", path="vault/todo/index.html", content=fixture("todo_unguarded.html"))],
            [tool("app_probe", app="todo")],
            [send("M15-LEDGER-DONE")],
        ]
        run = IterRun(script, name="m15ledger")
        vault = run.work / "vault"
        vault.mkdir()
        (run.root / ".runtime" / "settings.json").write_text(json.dumps({"vault": str(vault)}), encoding="utf-8")
        with run:
            run.say("Build me a todo app called todo. I add a todo by typing in #new-todo and clicking #add; each todo is an li in #list "
                    "with a .label, a .toggle button and a .delete button. Todos persist across a reload.")
            run.wait_for_reply("M15-LEDGER-DONE", timeout=900)
            run.stop()
            results = [m["content"] for m in run.experience() if m.get("role") == "tool"]
            written = next(c for c in results if "WROTE vault/todo/index.html" in c)
            self.assertIn("· ledger:", written)
            self.assertIn(".delete", written, "the ask named .delete; the file has none")
            self.assertIn("form-submit", written)
            atoms = run.atoms("state:build:todo:")
            self.assertTrue(any("ask-requires" in str(a) for a in atoms), atoms[:5])
            self.assertTrue(any("app-form-submit" in str(a) for a in atoms), "file facts in the store")
            requests = run.requests()
            ledgers = [r["system"] for r in requests if "[build ledger todo]" in r["system"]]
            self.assertTrue(ledgers, "the ledger reached the prompt")
            self.assertRegex(ledgers[-1], r"missing: [^\n]*\.delete")
            self.assertRegex(ledgers[-1], r"next: (build|probe)")


if __name__ == "__main__":
    unittest.main()
