#!/usr/bin/env python3
"""M12-D1: the builder's hands through the real loop (fake model, no Electron): write a plain app, read it
back numbered, edit one line, grep for it, write and run a tiny test, and see that browser_click is no
longer vetoed by the gate (it fails for the honest reason: no bridge in this harness).

Spec: docs/milestones/M12_builder_hands.md section D.
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from harness import IterRun, send, tool  # noqa: E402
from m12_support import pending, require_m12  # noqa: E402

PAGE = "<!doctype html><title>buildertest</title>\n<h1 id='title'>Builder test</h1>\n<button id='go'>Go</button>\n"
TINY_TEST = "def test_builder_ok():\n    assert 'go' in 'go'\n"


class BuilderHandsLoopTests(unittest.TestCase):
    def test_write_read_edit_grep_test_and_click_through_the_loop(self):
        require_m12()
        script = [
            [tool("write_file", path="buildertest/index.html", content=PAGE)],
            [tool("read_file", path="buildertest/index.html")],
            [tool("edit_file", path="buildertest/index.html", old="<button id='go'>Go</button>", new="<button id='go'>Start</button>")],
            [tool("grep_files", pattern="Start", path="buildertest")],
            [tool("write_file", path="../tests/test_m12_builder_tiny.py", content=TINY_TEST)],
            [tool("run_tests", target="tests/test_m12_builder_tiny.py")],
            [tool("browser_click", selector="#go")],
            [send("BUILDER-DONE")],
        ]
        run = IterRun(script, name="m12")
        (run.root.parent / "main.js").write_text("// repo root marker\n", encoding="utf-8")  # the parent is the repo root
        with run:
            run.say("build me a small page and test it")
            run.wait_for_reply("BUILDER-DONE", timeout=600)
            run.stop()
            # The loop stores each result as "Step <time>: [NACE advisory: …] <the tool's text>", so match the text.
            results = [m["content"] for m in run.experience() if m.get("role") == "tool"]
            self.assertTrue(any("WROTE buildertest/index.html (%d bytes, 3 lines)" % len(PAGE.encode("utf-8")) in c for c in results), results)
            self.assertTrue(any("buildertest/index.html (lines 1–3 of 3)\n    1| <!doctype html>" in c for c in results), results)
            self.assertTrue(any("EDITED buildertest/index.html (+1 −1 lines)" in c for c in results), results)
            self.assertTrue(any(c.rstrip().endswith("buildertest/index.html:3: <button id='go'>Start</button>") for c in results), results)
            self.assertTrue(any("RESULT: 1 passed" in c for c in results), results)
            click = next(c for c in results if "bridge" in c.lower() or "blocked" in c.lower())
            self.assertNotIn("Tool execution blocked by reasoning substrate", click, "the gate no longer vetoes click")
            self.assertIn("not running", click, "it failed for the real reason: no bridge in this harness")
            self.assertEqual((run.root / "buildertest" / "index.html").read_text(encoding="utf-8"), PAGE.replace("Go</button>", "Start</button>"))


if __name__ == "__main__":
    unittest.main()
