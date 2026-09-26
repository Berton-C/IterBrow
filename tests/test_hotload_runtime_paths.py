#!/usr/bin/env python3
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ITER = ROOT / "iter"
TOOLS = ITER / "tools"


class HotloadRuntimePathTests(unittest.TestCase):
    def test_both_iter_launch_paths_export_the_canonical_root_contract(self):
        main_source = (ROOT / "main.js").read_text(encoding="utf-8")
        iter_source = (ITER / "iter.py").read_text(encoding="utf-8")
        start = main_source.index("function startIterProcess()")
        end = main_source.index("function stopIter", start)
        self.assertIn("ITER_DIR,", main_source[start:end])
        self.assertIn('os.environ["ITER_DIR"] = str(ITER_ROOT)', iter_source)

    def _load_generation_copy(self, relative, canonical, generation, name):
        source = ITER / relative
        copied = generation / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        with mock.patch.dict(os.environ, {"ITER_DIR": str(canonical)}):
            spec = importlib.util.spec_from_file_location(name, copied)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module

    def test_relocated_components_keep_all_application_state_at_canonical_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            canonical = sandbox / "canonical" / "iter"
            generation = sandbox / "generation"
            canonical.mkdir(parents=True)
            canonical = canonical.resolve()
            wrong_cwd = sandbox / "wrong-cwd"
            wrong_cwd.mkdir()
            prior_cwd = Path.cwd()
            sys.path.insert(0, str(ITER))
            sys.path.insert(0, str(TOOLS))
            try:
                os.chdir(wrong_cwd)
                petta = self._load_generation_copy(
                    "tools/_petta_db.py", canonical, generation, "relocated_petta"
                )
                pwq = self._load_generation_copy(
                    "tools/pwq_write.py", canonical, generation, "relocated_pwq"
                )
                museum = self._load_generation_copy(
                    "tools/_component_museum.py", canonical, generation,
                    "relocated_museum",
                )
                capture = self._load_generation_copy(
                    "tools/device_capture.py", canonical, generation,
                    "relocated_capture",
                )
                gmail = self._load_generation_copy(
                    "tools/gmail_scan.py", canonical, generation, "relocated_gmail"
                )
                mattermost = self._load_generation_copy(
                    "tools/mm_scan.py", canonical, generation, "relocated_mattermost"
                )
                soul = self._load_generation_copy(
                    "transformations/soul_check.py", canonical, generation,
                    "relocated_soul",
                )
            finally:
                os.chdir(prior_cwd)
                sys.path = [p for p in sys.path if p not in (str(ITER), str(TOOLS))]

            self.assertEqual(Path(petta.DB_FILE), canonical / "chroma_db" / "memories.json")
            self.assertEqual(pwq.STORE.runtime_dir, canonical / ".runtime" / "pwq")
            self.assertEqual(Path(museum.MUSEUM_LOG), canonical / "memory" / "component_museum.jsonl")
            self.assertEqual(capture._CAPTURE_DIR, canonical / "memory" / "captures")
            self.assertEqual(capture._CAPTURE_HTML, canonical.parent / "renderer" / "capture.html")
            self.assertEqual(Path(gmail.CFG), canonical / "private" / "crm")
            self.assertEqual(Path(gmail.CAP), canonical / "crm" / "data" / "captures.json")
            self.assertEqual(Path(mattermost.CFG), canonical / "private" / "crm")
            self.assertEqual(Path(mattermost.CAP), canonical / "crm" / "data" / "captures.json")
            self.assertEqual(Path(soul.ROOT), canonical)
            self.assertFalse((generation / ".runtime").exists())
            self.assertFalse((generation / "chroma_db").exists())
            self.assertFalse((generation / "memory").exists())

    def test_cwd_is_the_direct_launch_fallback_when_iter_dir_is_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary)
            canonical = sandbox / "iter"
            generation = sandbox / "generation"
            canonical.mkdir()
            canonical = canonical.resolve()
            prior_cwd = Path.cwd()
            try:
                os.chdir(canonical)
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("ITER_DIR", None)
                    module = self._load_generation_copy_without_env(
                        "transformations/soul_check.py", generation,
                        "relocated_soul_cwd_fallback",
                    )
            finally:
                os.chdir(prior_cwd)
            self.assertEqual(Path(module.ROOT), canonical)

    def _load_generation_copy_without_env(self, relative, generation, name):
        source = ITER / relative
        copied = generation / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        spec = importlib.util.spec_from_file_location(name, copied)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


if __name__ == "__main__":
    unittest.main()
