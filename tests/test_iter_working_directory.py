#!/usr/bin/env python3
"""Every relative memory path resolves under ITER_DIR regardless of launch cwd (BUG-14)."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITER = ROOT / "iter"
SKIP = shutil.ignore_patterns("__pycache__", ".runtime", "*.pyc", "scratch", ".venv")


class IterWorkingDirectoryTests(unittest.TestCase):
    def test_bug14_worker_writes_episodic_files_under_iter_dir_not_launch_cwd(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            root = work / "iter"
            root.mkdir()
            for item in ("iterbrow_runtime", "tools", "transformations"):
                shutil.copytree(ITER / item, root / item, ignore=SKIP)
            shutil.copy2(ITER / "iter.py", root / "iter.py")
            payload = work / "payload.json"
            payload.write_text(json.dumps({"args": [[
                {"role": "system", "content": "s"},
                {"role": "user", "content": "Step 2026-10-01 09:00:00: [electron_ui] hello"}], []], "kwargs": {}}))
            launch = work / "elsewhere"
            launch.mkdir()
            for name in ("transcript", "history"):
                result = work / ("out_%s.json" % name)
                subprocess.run([sys.executable, str(root / "iter.py"), "--invoke",
                                str(root / "transformations" / (name + ".py")), "transform", str(result), str(payload)],
                               cwd=str(launch), check=True, timeout=60,
                               env={"PATH": "/usr/bin:/bin", "ITER_DIR": str(root), "PYTHONDONTWRITEBYTECODE": "1"})
                self.assertTrue(json.loads(result.read_text())["ok"], result.read_text())
            self.assertEqual(sorted(p.name for p in launch.iterdir()), [])
            self.assertIn("hello", (root / "transcript.txt").read_text())
            self.assertIn("hello", (root / "history.metta").read_text())


if __name__ == "__main__":
    unittest.main()
