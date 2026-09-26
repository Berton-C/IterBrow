#!/usr/bin/env python3
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "scripts" / "iterbrow_readiness.py"


def _load_readiness():
    spec = importlib.util.spec_from_file_location("iterbrow_readiness", READINESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallerReadinessTests(unittest.TestCase):
    def test_virtualenv_executable_is_not_dereferenced(self):
        readiness = _load_readiness()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "base-python"
            target.write_text("", encoding="utf-8")
            venv_python = root / "venv-python"
            venv_python.symlink_to(target)
            self.assertEqual(readiness._executable_path(venv_python), venv_python)
            self.assertNotEqual(readiness._executable_path(venv_python), target)

    def test_installed_state_explains_start_without_claiming_app_is_closed(self):
        readiness = _load_readiness()
        report = readiness.assess_readiness({
            "installed": {
                "program_files": True,
                "lockfiles": True,
                "node_runtime": True,
                "electron_assets": True,
                "python_runtime": True,
                "hyperon_import": True,
                "state_manifest": True,
            },
            "expected_iter_dir": "/tmp/iter-readiness-test",
        })
        self.assertEqual(report["state"], "installed")
        self.assertIn("open IterBrow if needed", report["next_action"])
        self.assertIn("press Start", report["next_action"])


if __name__ == "__main__":
    unittest.main()
