#!/usr/bin/env python3
"""M12-A1..A4: untie the hands — the gate advises by default, the quarantine is lifted, refusals are not
failures, and the build-and-verify tools are never hidden.

Spec: docs/milestones/M12_builder_hands.md section A.
"""
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m12_support import (pending, require_m12, m12_root, tool_text, lifecycle_seed, gate_source, main_js,  # noqa: E402
                         BUILD_TOOLS, ITER_SRC, REPO)

PYTHON = str(REPO / "iter" / ".venv" / "bin" / "python3")


class GateDefaultTests(unittest.TestCase):
    """M12-A1"""

    def test_advisory_is_the_default_in_both_places(self):
        require_m12()
        self.assertIn("process.env.METTA_GATE_MODE || 'advisory'", main_js())
        src = gate_source()
        self.assertRegex(src, r'os\.environ\.get\("METTA_GATE_MODE",\s*"advisory"\)')
        self.assertNotRegex(src, r'mode = "enforce"\s*\n', "an unknown mode value falls back to advisory, not enforce")
        self.assertIn('default "advisory"', src)

    def test_gate_advises_a_quarantined_capability_instead_of_vetoing(self):
        """With no env set and a seed that still quarantines a capability, the verdict is ADVISE."""
        r = m12_root("m12gate")
        self.addCleanup(r.close)
        (r.root / "capability_lifecycle.metta").write_text(
            lifecycle_seed() + "\n(cap-lifecycle browser_click quarantined)\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "METTA_GATE_MODE"}
        env.update({"ITER_DIR": str(r.root)})
        out = subprocess.run([PYTHON, "-c", "import sys; sys.path.insert(0, 'tools'); import _metta_gate; print(_metta_gate.run('browser_click', {}))"],
                             cwd=str(r.root), env=env, capture_output=True, text=True, timeout=60)
        verdict = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else out.stderr
        mode, action = verdict.split("|")[:2]
        self.assertEqual((mode, action), ("advisory", "ADVISE"), verdict)
        env["METTA_GATE_MODE"] = "enforce"
        out = subprocess.run([PYTHON, "-c", "import sys; sys.path.insert(0, 'tools'); import _metta_gate; print(_metta_gate.run('browser_click', {}))"],
                             cwd=str(r.root), env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.stdout.strip().splitlines()[-1].split("|")[1], "VETO", "enforce still works when asked for")


class QuarantineTests(unittest.TestCase):
    """M12-A2"""

    def test_no_capability_is_quarantined_by_seed(self):
        require_m12()
        seed = lifecycle_seed()
        self.assertNotRegex(seed, r"(?m)^\(cap-lifecycle \S+ quarantined\)", "no live quarantine lines (comments may remain)")
        self.assertRegex(seed, r"(?i)lifted", "the comment says the lines were lifted and why")
        for cap in ("browser_click", "browser_type", "browser_cdp"):
            self.assertNotRegex(seed, r"(?m)^\(cap-lifecycle %s " % cap, cap)


class RefusalTests(unittest.TestCase):
    """M12-A3"""

    def test_a_lock_refusal_is_a_refused_result_not_a_failure(self):
        """A fake bridge answers every call with the lock message; the tool returns success=None."""
        require_m12()
        r = m12_root("m12refuse")
        self.addCleanup(r.close)
        sock = r.root / ".runtime" / "fake-bridge.sock"
        server = subprocess.Popen([PYTHON, "-c", """
import socket, os, json, sys
path = sys.argv[1]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.bind(path); s.listen(5)
while True:
    c, _ = s.accept(); c.recv(65536)
    c.sendall((json.dumps({"ok": False, "error": "Tab 3 is locked by the user and cannot be modified. Ask the user to click the tab's lock icon."}) + "\\n").encode()); c.close()
""", str(sock)])
        self.addCleanup(server.kill)
        for _ in range(50):
            if sock.exists():
                break
            import time; time.sleep(0.05)
        result = r.tool("browser_click", env={"ITER_BRIDGE_SOCKET": str(sock)}, selector="#go")
        self.assertTrue(result.get("ok"), result)
        self.assertIn("locked by the user", result.get("result", ""))
        execution = result.get("execution_outcome") or result.get("execution")
        self.assertEqual((execution or {}).get("state"), "refused", result)
        self.assertIsNone((execution or {}).get("success"), "a refusal moves no belief")

    def test_navigate_reports_a_load_error_as_a_failure(self):
        src = (ITER_SRC / "tools" / "browser_navigate.py").read_text(encoding="utf-8")
        self.assertRegex(src, r"ToolOutput\([^)]*False", "a bridge warning is a failed navigation, not success text")

    def test_tracker_and_courier_are_untouched(self):
        """A guard, not a feature: green today and it must stay green (M12-A3 touches tools, never NACE)."""
        for rel in ("iter/transformations/tool_reliability_tracker.py", "iter/transformations/nace_courier.py"):
            diff = subprocess.run(["git", "diff", "--stat", "eea6737", "--", rel], cwd=str(REPO), capture_output=True, text=True)
            self.assertEqual(diff.stdout.strip(), "", rel + " changed since the M11 scope commit")


class HiddenToolsTests(unittest.TestCase):
    """M12-A4"""

    def test_build_and_verify_tools_are_protected_from_hiding(self):
        require_m12()
        src = (ITER_SRC / "transformations" / "dynamic_tool_budget.py").read_text(encoding="utf-8")
        block = src[src.index("PROTECTED_TOOLS"):src.index("}", src.index("PROTECTED_TOOLS")) + 1]
        for name in BUILD_TOOLS + ["browser_click", "browser_type", "browser_scroll", "browser_eval", "browser_read_text",
                                   "browser_navigate", "browser_new_tab", "browser_close_tab"]:
            self.assertIn('"%s"' % name, block, name)


if __name__ == "__main__":
    unittest.main()
