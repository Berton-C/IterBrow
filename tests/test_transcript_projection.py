#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "iter" / "transformations" / "transcript.py"


class TranscriptProjectionTests(unittest.TestCase):
    def test_send_content_is_preserved_in_transcript(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            spec = importlib.util.spec_from_file_location(
                "transcript_projection_under_test", SOURCE
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.LOG_PATH = str(target / "transcript.txt")
            module.STATE_PATH = str(target / ".transcript_state")
            tool_call_id = "call-chat-proof"
            messages = [
                {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": tool_call_id,
                        "function": {
                            "name": "send",
                            "arguments": json.dumps({
                                "channel": "electron_ui",
                                "content": "CHAT-DELIVERY-PROOF",
                            }),
                        },
                    }],
                },
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": "Step 2026-09-22 00:00:00: SUCCESS",
                },
            ]

            module.transform(messages, [])

            transcript = (target / "transcript.txt").read_text(encoding="utf-8")
            self.assertEqual(
                transcript,
                "[2026-09-22 00:00:00][send -> electron_ui] CHAT-DELIVERY-PROOF\n",
            )


if __name__ == "__main__":
    unittest.main()
