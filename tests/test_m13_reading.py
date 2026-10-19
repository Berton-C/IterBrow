#!/usr/bin/env python3
"""M13-A1..A2: reading at size — the wire allowance for reading tools and the one-line advisory.

Spec: docs/milestones/M13_builder_eyes.md section A.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m13_support import pending, require_m13, ITER_SRC  # noqa: E402

sys.path.insert(0, str(ITER_SRC))


class WireAllowanceTests(unittest.TestCase):
    """M13-A1"""

    def test_reading_tools_get_a_24k_wire_and_others_keep_4500(self):
        require_m13()
        from iterbrow_runtime import tool_results
        self.assertEqual(tool_results.READ_WIRE_CHARS, 24000)
        self.assertEqual(tool_results.WIRE_CHARS, 4500)
        text = "x" * 20000
        with tempfile.TemporaryDirectory() as temp:
            kept = tool_results.capture_tool_output(temp, text, tool_call_id="c1", tool_name="read_file",
                                                    generation_id="g", max_chars=24000)
            self.assertEqual(kept, text, "a 20k read passes through whole under the reading wire")
            cut = tool_results.capture_tool_output(temp, text, tool_call_id="c2", tool_name="shell",
                                                   generation_id="g", max_chars=4500)
            self.assertNotEqual(cut, text)
            self.assertIn("retained_tool_output", cut)
        src = (ITER_SRC / "iter.py").read_text(encoding="utf-8")
        self.assertIn("READ_TOOLS", src)
        block = src[src.index("READ_TOOLS"):src.index("READ_TOOLS") + 400]
        for name in ("read_file", "grep_files", "list_files", "browser_read_text", "run_tests", "read_tool_result"):
            self.assertIn('"%s"' % name, block, name)
        self.assertIn("READ_WIRE_CHARS", src)


class AdvisoryTests(unittest.TestCase):
    """M13-A2"""

    def test_short_note(self):
        require_m13()
        from iterbrow_runtime.advisory import short_note
        candidate = ("capability 'write_file' is trust_stage=candidate (no cap-efficacy belief data yet) -- always surfaced, "
                     "never a silent fail-open ALLOW while untested [decision=2fd83f74 evaluated_state=1 decision_saved_at=2]")
        self.assertEqual(short_note("write_file", candidate), "[NACE: 'write_file' has no track record yet] ")
        low = ("efficacy expectation 0.212 < 0.30 threshold for 'websearch' (authoritative) -- advise only "
               "[decision=abc evaluated_state=9 decision_saved_at=10]")
        self.assertEqual(short_note("websearch", low), "[NACE advisory: efficacy expectation 0.212 < 0.30 threshold for 'websearch' (authoritative)] ")
        long = "a" * 300
        note = short_note("x", long)
        self.assertLessEqual(len(note), len("[NACE advisory: ] ") + 160)
        self.assertEqual(short_note("x", ""), "")
        src = (ITER_SRC / "iter.py").read_text(encoding="utf-8")
        self.assertIn("short_note(", src)
        self.assertNotIn('gate_note = f"[NACE advisory: {gate_detail}] "', src)


if __name__ == "__main__":
    unittest.main()
