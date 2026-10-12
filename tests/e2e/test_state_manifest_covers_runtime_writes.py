#!/usr/bin/env python3
"""Invariant: every file the running agent writes under ITER_DIR is covered by
state_manifest.json, so Export/Import/Reset can never silently skip memory.

Code roots and the virtualenv are not state.  Anything else that appears on
disk after a short real run must match a manifest entry (exact path or a
directory prefix)."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import IterRun, COPY, send, nop, tool

CODE_ROOTS = set(COPY) | {".venv"}


def undeclared_paths(iter_root, manifest):
    declared = [entry["path"].rstrip("/") for entry in manifest["entries"]]
    seen = []
    for path in sorted(Path(iter_root).rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(iter_root).as_posix()
        top = relative.split("/", 1)[0]
        if top in CODE_ROOTS or "__pycache__" in relative:
            continue
        if any(relative == d or relative.startswith(d + "/") for d in declared):
            continue
        seen.append(relative)
    return seen


class ManifestCoversRuntimeWritesTests(unittest.TestCase):



    def test_every_runtime_written_path_is_declared(self):
        # Exercise the memory writers as well as the conversation loop.
        script = [
            [tool("start_new_task", person="tester", requestchannel="electron_ui",
                  taskcontent="remember the codeword", completionsendcriterium="codeword confirmed",
                  originalUserMessage="say hello twice", new_work="true"),
             send("hello-0")],
            [tool("remember", text="The codeword is PELICAN.", mem_type="fact"),
             tool("pin", message="working on: codeword")],
            [tool("chroma_query", query="what is the codeword?", k=3),
             tool("reminder", when="2099-01-01 00:00", channel="electron_ui", message="far future")],
            [send("hello-1")],
            [nop(5)],
        ]
        with IterRun(script, name="manifest") as run:
            run.say("say hello twice")
            run.wait_for_reply("hello-1")
            run.wait_for_requests(5)
            run.stop()
            # The scenario only means something if the memory writers really ran.
            results = {m["tool_call_id"]: m["content"] for m in run.experience() if m["role"] == "tool"}
            self.assertIn("REMEMBER-SUCCESS", results.get("call_1_0", ""), results)
            self.assertIn("PELICAN", results.get("call_2_0", ""), results)
            self.assertTrue(run.read("memory/tasks/current_tasks.txt"), "start_new_task wrote nothing")
            manifest = json.loads(run.read("state_manifest.json"))
            missing = undeclared_paths(run.root, manifest)
        self.assertEqual(missing, [], "written but not declared in state_manifest.json:\n  "
                         + "\n  ".join(missing))


if __name__ == "__main__":
    unittest.main()
