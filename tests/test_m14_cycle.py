#!/usr/bin/env python3
"""M14-F1..F3: every transformation of a cycle runs in one worker process; tools keep their own.

Spec: docs/milestones/M14_vault_and_foundry_loop.md section F. The batch worker is run directly
(`iter.py --invoke-batch manifest result`) over three fake transformations.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m14_support import pending, require_m14, ITER_SRC  # noqa: E402
from semantic_memory_support import PYTHON  # noqa: E402

FAKES = {
    "a_first.py": """import os
DESCRIPTION = "fake"
def transform(messages, tools):
    messages[0]["content"] += " [a pid=%d]" % os.getpid()
    return messages, tools
""",
    "b_raises.py": """DESCRIPTION = "fake"
def transform(messages, tools):
    raise ValueError("boom")
""",
    "c_sleeps.py": """import time
DESCRIPTION = "fake"
def transform(messages, tools):
    time.sleep(30)
    return messages, tools
""",
    "d_last.py": """import os
DESCRIPTION = "fake"
def transform(messages, tools):
    messages[0]["content"] += " [d pid=%d]" % os.getpid()
    return messages, [t for t in tools if t.get("name") != "dropme"]
""",
}


class BatchWorkerTests(unittest.TestCase):
    """M14-F1"""

    def _run_batch(self, timeout_c=1):
        work = Path(tempfile.mkdtemp(prefix="m14batch-"))
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(work)]))
        trans = work / "transformations"
        trans.mkdir()
        for name, body in FAKES.items():
            (trans / name).write_text(body, encoding="utf-8")
        payload = work / "payload.json"
        payload.write_text(json.dumps({"args": [[{"role": "system", "content": "sys"}], [{"name": "send"}, {"name": "dropme"}]], "kwargs": {}}), encoding="utf-8")
        manifest = work / "manifest.json"
        manifest.write_text(json.dumps({"payload": str(payload), "items": [
            {"path": str(trans / "a_first.py"), "timeout": 15}, {"path": str(trans / "b_raises.py"), "timeout": 15},
            {"path": str(trans / "c_sleeps.py"), "timeout": timeout_c}, {"path": str(trans / "d_last.py"), "timeout": 15}]}), encoding="utf-8")
        result = work / "result.json"
        started = time.monotonic()
        proc = subprocess.run([PYTHON, str(ITER_SRC / "iter.py"), "--invoke-batch", str(manifest), str(result)],
                              cwd=str(ITER_SRC), env=dict(os.environ, ITER_DIR=str(ITER_SRC)), capture_output=True, text=True, timeout=60)
        return proc, json.loads(result.read_text(encoding="utf-8")), time.monotonic() - started

    @pending("M14-F1")
    def test_one_process_runs_them_all_in_order_with_isolation_per_item(self):
        require_m14()
        proc, out, elapsed = self._run_batch()
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        items = out["items"]
        self.assertEqual([Path(i["path"]).name for i in items], ["a_first.py", "b_raises.py", "c_sleeps.py", "d_last.py"])
        self.assertTrue(items[0]["ok"])
        self.assertFalse(items[1]["ok"])
        self.assertIn("ValueError: boom", items[1]["error"])
        self.assertFalse(items[2]["ok"])
        self.assertRegex(items[2]["error"], r"TIMEOUT after 1s in c_sleeps\.transform")
        self.assertTrue(items[3]["ok"])
        self.assertLess(elapsed, 10, "the sleeper was stopped by its own timeout, not the batch's")
        for item in items:
            self.assertIn("seconds", item)
        messages, tools = out["result"]
        pids = re.findall(r"pid=(\d+)", messages[0]["content"])
        self.assertEqual(len(pids), 2)
        self.assertEqual(pids[0], pids[1], "a and d ran in the same process")
        self.assertEqual(int(pids[0]), out["pid"])
        self.assertNotEqual(int(pids[0]), os.getpid())
        self.assertEqual([t["name"] for t in tools], ["send"], "d's returned tools reached the result; b and c changed nothing")
        self.assertEqual(messages[0]["content"].count("[a pid"), 1)

    @pending("M14-F1")
    def test_loop_uses_the_batch_and_falls_back_per_process(self):
        require_m14()
        src = (ITER_SRC / "iter.py").read_text(encoding="utf-8")
        self.assertIn('sys.argv[1] == "--invoke-batch"', src)
        self.assertIn("def invoke_dynamic_batch(", src)
        apply = src[src.index("def apply_transformation("):src.index("# 4. Main loop")]
        self.assertIn("invoke_dynamic_batch(", apply)
        self.assertIn("[transformations] batch worker failed", apply)
        self.assertIn("invoke_dynamic(path, \"transform\"", apply, "per-process remains the fallback")
        self.assertIn("TRANSFORMATION_HEALTH_FAILURE", apply)
        self.assertIn("_batch_seconds", apply)
        self.assertIn("transformations_processes", src)
        worker = src[src.index("def dynamic_worker("):src.index("def invoke_dynamic(")]
        self.assertNotIn("--invoke-batch", worker, "tool runs keep their own process and their own worker")


if __name__ == "__main__":
    unittest.main()
