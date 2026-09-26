#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ITER = ROOT / "iter"
sys.path.insert(0, str(ITER))

from tools._metadata_static import static_tool_metadata


class ToolMetadataTests(unittest.TestCase):
    def test_defaults_are_optional_and_variadics_are_not_json_properties(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tool = root / "fixture.py"
            result_path = root / "result.json"
            payload_path = root / "payload.json"
            tool.write_text(
                'DESCRIPTION = "fixture"\n\n'
                'def run(required, optional="default", *extras, keyword="value", **kwargs):\n'
                '    return required\n',
                encoding="utf-8",
            )
            payload_path.write_text('{"args": [], "kwargs": {}}', encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable, str(ITER / "iter.py"), "--invoke",
                    str(tool), "__tool_metadata__", str(result_path), str(payload_path),
                ],
                cwd=root, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            dynamic = json.loads(result_path.read_text(encoding="utf-8"))["result"]
            expected = {
                "description": "fixture",
                "parameters": ["required", "optional", "keyword"],
                "required": ["required"],
            }
            self.assertEqual(dynamic, expected)
            self.assertEqual(static_tool_metadata(tool), expected)


if __name__ == "__main__":
    unittest.main()
