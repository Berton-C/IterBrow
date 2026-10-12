#!/usr/bin/env python3
"""Regression tests for the episodic memory pipeline (recap -> episodes -> tiers).

Each test runs the real component code from this repository against a fresh
temporary ITER_DIR (the components use cwd-relative paths, exactly as iter.py's
dynamic worker runs them).  Test names carry the audit bug ID they guard.
"""
import importlib.util
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITER = ROOT / "iter"
for _path in (ITER / "tools", ITER):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

_COUNTER = itertools.count()


def load(relative):
    """Load a component by path, as iter.py --invoke does (fresh module each time)."""
    path = ITER / relative
    spec = importlib.util.spec_from_file_location(
        "_episodic_test_%d_%s" % (next(_COUNTER), path.stem), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def roundtrip(messages):
    """iter.py hands transformations a JSON copy of the request."""
    return json.loads(json.dumps(messages))


def system(text="prompt.txt:\nYou are Iter."):
    return {"role": "system", "content": text}


def user(ts, text, channel="electron_ui"):
    return {"role": "user", "content": "Step %s: [%s] %s" % (ts, channel, text)}


def send_exchange(call_id, ts, text):
    return [{"role": "assistant", "content": "", "tool_calls": [{
                "id": call_id, "type": "function",
                "function": {"name": "send", "arguments": json.dumps({"channel": "electron_ui", "content": text})}}]},
            {"role": "tool", "tool_call_id": call_id, "content": "Step %s: SUCCESS" % ts,
             "_iter_execution": {"success": True}}]


def tool_exchange(call_id, name, ts, result="ok", arguments="{}"):
    return [{"role": "assistant", "content": "", "tool_calls": [{
                "id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}]},
            {"role": "tool", "tool_call_id": call_id, "content": "Step %s: %s" % (ts, result)}]


class EpisodicCase(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._iter_dir = os.environ.get("ITER_DIR")
        self.dir = Path(tempfile.mkdtemp(prefix="ib-episodic-"))
        (self.dir / "memory").mkdir()
        os.chdir(self.dir)
        os.environ["ITER_DIR"] = str(self.dir)

    def tearDown(self):
        os.chdir(self._cwd)
        if self._iter_dir is None:
            os.environ.pop("ITER_DIR", None)
        else:
            os.environ["ITER_DIR"] = self._iter_dir
        shutil.rmtree(self.dir, ignore_errors=True)

    def write_episodes(self, numbers, name="episode_%04d.json", text=lambda i: "ep %d" % i):
        recap = self.dir / "memory" / "recap"
        recap.mkdir(parents=True, exist_ok=True)
        for i in numbers:
            (recap / (name % i)).write_text(json.dumps({"e": i, "s": text(i)}, ensure_ascii=False), encoding="utf-8")

    def tier(self, name):
        path = self.dir / "memory" / "tiers" / (name + ".txt")
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def tiers(self):
        return {name: self.tier(name) for name in ("tier3", "tier4", "tier5")}


# ---------------------------------------------------------------- BUG-4
class EpisodeOrderTests(EpisodicCase):
    def test_bug4_rebuild_orders_episodes_numerically_not_lexicographically(self):
        self.write_episodes(range(1, 13), name="episode_%d.json")
        load("tools/rebuild_tiers.py").rebuild()
        self.assertEqual(self.tier("tier5"), "12 episodes recorded, E1 to E12.")
        self.assertTrue(self.tier("tier3").splitlines()[-1].startswith("E12"), self.tier("tier3"))

    def test_bug4_recap_block_lists_episodes_in_numeric_order(self):
        self.write_episodes([9, 10, 11], name="episode_%d.json")
        messages, _ = load("transformations/recap.py").transform([system()], [])
        content = messages[0]["content"]
        self.assertLess(content.index("### E9"), content.index("### E10"))
        self.assertLess(content.index("### E10"), content.index("### E11"))

    def test_bug4_order_uses_e_field_and_tolerates_gaps(self):
        # Owner's live data: episodes 1-25 are missing.
        self.write_episodes(range(26, 75))
        load("tools/rebuild_tiers.py").rebuild()
        self.assertEqual(self.tier("tier5"), "49 episodes recorded, E26 to E74.")


if __name__ == "__main__":
    unittest.main()
