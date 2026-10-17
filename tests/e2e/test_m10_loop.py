#!/usr/bin/env python3
"""M10-D1 invariant: through the real loop, a brief and then ally_sdk give a plain app the SDK,
idempotently; the catalog lists the app with its brief. (That the tool touches nothing outside
the app is checked at unit level, where only the tool runs.)

Spec: docs/milestones/M10_ally_sdk.md section D.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import IterRun, send, tool  # noqa: E402
from m10_support import pending, require_m10, make_app_dir, SDK, KERNEL_JSON  # noqa: E402


class AllySdkLoopTests(unittest.TestCase):
    @pending("M10-D1")
    def test_brief_then_sdk_through_the_loop(self):
        require_m10()
        script = [
            [tool("brief", app="mapstation", for_whom="Berton, finding his way in a new city", flourishing="he looks up from the map")],
            [tool("ally_sdk", app="mapstation")],
            [tool("ally_sdk", app="mapstation")],
            [tool("apps")],
            [send("SDK-DONE")],
        ]
        run = IterRun(script, name="m10")
        app = make_app_dir(run.root, "mapstation", body="<div id='map'></div>\n<script>window.map = 1;</script>\n")
        (run.root / ".runtime" / "soul_settings.json").write_text(json.dumps({"schema_version": 1, "person": "berton",
                                                                               "people": {"berton": {"features": {"brief": True}}}}))
        with run:
            run.say("give mapstation the ally")
            run.wait_for_reply("SDK-DONE", timeout=420)
            run.stop()
            results = [m["content"] for m in run.experience() if m.get("role") == "tool"]
            self.assertTrue(any("ALLY-SDK: installed in mapstation" in c for c in results), results)
            self.assertTrue(any("ALLY-SDK: already installed in mapstation" in c for c in results), results)
            self.assertEqual((app / "iter_ally.js").read_bytes(), SDK.read_bytes())
            self.assertEqual((app / "soul_kernel.json").read_bytes(), KERNEL_JSON.read_bytes())
            html = (app / "index.html").read_text()
            self.assertIn('<script src="iter_ally.js"></script>', html)
            self.assertIn('brief: {for: "Berton, finding his way in a new city", flourishing: "he looks up from the map"}', html)
            self.assertTrue(html.startswith("<!doctype html><title>mapstation</title><div id='map'></div>\n<script>window.map = 1;</script>"))
            listing = next(c for c in results if "mapstation (plain)" in c)
            self.assertIn("— for Berton, finding his way in a new city", listing)


if __name__ == "__main__":
    unittest.main()
