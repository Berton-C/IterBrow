#!/usr/bin/env python3
"""Invariant: semantic memory reported as stored is in the AtomSpace authority,
and chroma_db is exactly the authority's search index, rebuildable from it.

Through the real loop, real AtomSpace and the fake model: remember, support,
link_episode, memory_update, forget, remember again. Then (a) every reported
success is a committed AtomSpace event and the final state is right, (b) the
index ids equal the authority ids, (c) with the service restarted and
chroma_db deleted, chroma_query (run by iter.py's own dynamic worker) finds the
remembered fact again, rebuilt from the authority."""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import IterRun, PYTHON, atomspace_call, send, tool

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "iter"))
from iterbrow_runtime.cognitive_events import parse_semantic_atom  # noqa: E402

FACT = "The e2e cat is named Miso."
EP1, EP2 = "2026-10-12 10:00:00", "2026-10-12 11:00:00"


def invoke(run, tool_name, **kwargs):
    """Run a tool exactly the way the loop does: iter.py --invoke (dynamic worker)."""
    work = Path(tempfile.mkdtemp(prefix="iterbrow-invoke-"))
    try:
        payload, result = work / "payload.json", work / "result.json"
        payload.write_text(json.dumps({"args": [], "kwargs": kwargs}))
        subprocess.run([PYTHON, str(run.root / "iter.py"), "--invoke", str(run.root / "tools" / (tool_name + ".py")),
                        "run", str(result), str(payload)], cwd=str(run.root), env=run.env(), timeout=120,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return json.loads(result.read_text())
    finally:
        shutil.rmtree(work, ignore_errors=True)


class SemanticMemoryAuthorityTests(unittest.TestCase):
    def test_reported_successes_are_authoritative_and_the_index_rebuilds(self):
        script = [
            [tool("remember", text=FACT, mem_type="belief")],
            [tool("support", item_id="{{memory_id}}", episode_time=EP1)],
            [tool("link_episode", item_id="{{memory_id}}", linked_time=EP2)],
            [tool("memory_update", item_id="{{memory_id}}", text=FACT + " She is grey.")],
            [tool("forget", item_id="{{memory_id}}", force="true")],
            [tool("remember", text=FACT, mem_type="belief")],
            [send("E2E-SEMANTIC-DONE")],
        ]
        with IterRun(script, name="semantic") as run:
            run.say("remember facts about the cat")
            run.wait_for_reply("E2E-SEMANTIC-DONE", timeout=420)  # six tool rounds; the default 180s is tight on a slow box
            run.stop()
            log = run.read_log("iter.log")
            calls = {}
            for message in run.experience():
                for call in message.get("tool_calls") or []:
                    calls[call["id"]] = (call["function"]["name"], json.loads(call["function"]["arguments"]))
            results = [(calls.get(m["tool_call_id"], ("?", {})), m["content"])
                       for m in run.experience() if m["role"] == "tool"]
            outcome = {name: content for (name, _), content in results}
            remembered = [content for (name, _), content in results if name == "remember"]
            self.assertEqual(len(remembered), 2, log)
            for content in remembered:
                self.assertIn("REMEMBER-SUCCESS", content, log)
            first, second = (c.split("stored ")[1].split()[0] for c in remembered)
            self.assertNotEqual(first, second)
            for name, marker in (("support", "SUPPORT-SUCCESS"), ("link_episode", "LINK-SUCCESS"),
                                 ("memory_update", "MEMORY-UPDATE-SUCCESS"), ("forget", "FORGET-SUCCESS")):
                self.assertIn(marker, outcome.get(name, ""), "%s: %r\n%s" % (name, outcome.get(name), log))
                self.assertIn(first, [args.get("item_id") for (n, args), _ in results if n == name])

            # (a) every reported success is a committed AtomSpace event ...
            events = run.atoms("event:memory:")
            def committed(kind, item_id):
                return [k for k in events if k.startswith("event:memory:%s:%s:" % (kind, item_id))]
            self.assertEqual(len(committed("remembered", first)), 1)
            self.assertEqual(len(committed("memory_updated", first)), 3)  # support, link, update
            self.assertEqual(len(committed("forgotten", first)), 1)
            self.assertEqual(len(committed("remembered", second)), 1)
            # ... and the final state is what the successes claim.
            atoms = run.atoms("state:semantic_memory:")
            memories = {}
            for key, atom in atoms.items():
                item_id, document, metadata = parse_semantic_atom(key, atom)
                memories[item_id] = (document, metadata)
            self.assertEqual(set(memories), {second})
            self.assertEqual(memories[second][0], FACT)
            self.assertEqual(memories[second][1]["mem_type"], "belief")

            # (b) the index is exactly the authority's id set.
            index = json.loads(run.read("chroma_db/memories.json"))
            self.assertEqual(set(index["ids"]), set(memories))

            # (c) stop the service, delete chroma_db, restart: search rebuilds from the authority.
            run.service.terminate()
            run.service.wait(15)
            shutil.rmtree(run.root / "chroma_db")
            run.service = subprocess.Popen([PYTHON, str(run.root / "metta_server.py")], cwd=str(run.root),
                                           env=run.env(), stdout=run.service_log, stderr=run.service_log,
                                           stdin=subprocess.DEVNULL)
            deadline = time.time() + 120
            while time.time() < deadline:
                try:
                    if atomspace_call(run.sock, "status", timeout=1).get("ready"):
                        break
                except Exception:
                    pass
                time.sleep(0.2)
            found = invoke(run, "chroma_query", query="what is the cat called?", k=3)
            self.assertTrue(found.get("ok"), found)
            self.assertIn("Content: " + FACT, found["result"])
            self.assertIn("ID: " + second, found["result"])
            index = json.loads(run.read("chroma_db/memories.json"))
            self.assertEqual(set(index["ids"]), {second})


if __name__ == "__main__":
    unittest.main()
