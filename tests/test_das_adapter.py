#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iter"))

from iterbrow_runtime.das_adapter import DASProjectionWorker  # noqa: E402


class DASAdapterTests(unittest.TestCase):
    def test_disabled_is_non_authoritative_and_does_not_poll(self):
        with tempfile.TemporaryDirectory() as temp:
            worker = DASProjectionWorker(lambda _after, _limit: [], temp)
            worker.start()
            status = worker.status()
            self.assertEqual(status["adapter"], "disabled")
            self.assertFalse(status["authoritative"])
            self.assertFalse(status["running"])

    def test_file_adapter_advances_only_after_apply(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
            os.environ, {"ITER_DAS_ADAPTER": "file"}, clear=False
        ):
            events = [{
                "epoch": "e1", "commit": 1, "transaction_id": "t1",
                "operations": [], "metadata": {}, "state_hash": "h",
            }]
            worker = DASProjectionWorker(lambda after, _limit: events if after < 1 else [], temp)
            self.assertEqual(worker.run_once(), 1)
            self.assertEqual(worker.status()["cursor"], {"epoch": "e1", "commit": 1})
            lines = (Path(temp) / "das_projection" / "events.jsonl").read_text().splitlines()
            self.assertEqual(json.loads(lines[0])["transaction_id"], "t1")
            self.assertEqual(worker.run_once(), 0)
            self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
