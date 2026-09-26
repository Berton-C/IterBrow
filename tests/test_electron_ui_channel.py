#!/usr/bin/env python3
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHANNEL_SOURCE = ROOT / "iter" / "channels" / "electron_ui.py"


class ElectronUiChannelTests(unittest.TestCase):
    def test_hotload_copy_consumes_canonical_runtime_inbox(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "iter"
            generation_channel = (
                root / "generation" / "channels" / "electron_ui.py"
            )
            generation_channel.parent.mkdir(parents=True)
            generation_channel.write_text(
                CHANNEL_SOURCE.read_text(encoding="utf-8"), encoding="utf-8"
            )
            inbox = canonical / ".runtime" / "electron_ui" / "inbox"
            inbox.mkdir(parents=True)
            queued = inbox / "0001.txt"
            queued.write_text("system health status please.", encoding="utf-8")

            with mock.patch.dict(os.environ, {"ITER_DIR": str(canonical)}):
                spec = importlib.util.spec_from_file_location(
                    "hotloaded_electron_ui", generation_channel
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.assertEqual(module.receive(), "system health status please.")

            self.assertFalse(queued.exists())
            self.assertFalse(
                (root / "generation" / ".runtime" / "electron_ui").exists()
            )

    def test_send_publishes_a_complete_envelope_atomically(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "iter"
            generation_channel = (
                root / "generation" / "channels" / "electron_ui.py"
            )
            generation_channel.parent.mkdir(parents=True)
            generation_channel.write_text(
                CHANNEL_SOURCE.read_text(encoding="utf-8"), encoding="utf-8"
            )

            with mock.patch.dict(os.environ, {"ITER_DIR": str(canonical)}):
                spec = importlib.util.spec_from_file_location(
                    "hotloaded_electron_ui_send", generation_channel
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.send("reply body")

            outbox = canonical / ".runtime" / "electron_ui" / "outbox"
            queued = list(outbox.iterdir())
            self.assertEqual(len(queued), 1)
            envelope = json.loads(queued[0].read_text(encoding="utf-8"))
            self.assertEqual(envelope["schema_version"], 1)
            self.assertEqual(envelope["role"], "iter")
            self.assertEqual(envelope["content"], "reply body")
            self.assertTrue(envelope["id"].startswith("iter-"))
            staging = canonical / ".runtime" / "electron_ui" / "staging"
            self.assertEqual(list(staging.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
