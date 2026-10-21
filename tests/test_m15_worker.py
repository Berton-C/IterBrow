#!/usr/bin/env python3
"""M15-D1..D2 (DEFERRED — not in this milestone; runs only with ITERBROW_M15_WORKER=1): the warm query worker — one isolated Hyperon process per view, kept current with the store's
deltas, so a per-cycle MeTTa query costs milliseconds instead of a rebuild.

Spec: docs/milestones/M15_build_ledger.md section D. Needs the real Hyperon (the worker is a subprocess).
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m15_support import pending, require_m15, hyperon_available, ITER_SRC  # noqa: E402


def _space(temp):
    sys.path.insert(0, str(ITER_SRC))
    import metta_server
    (temp / "seed.metta").write_text("(declared seed)\n(= (double $x) (* 2 $x))\n", encoding="utf-8")
    manifest_path = temp / "state_manifest.json"
    manifest_path.write_text(json.dumps({"schema_version": 1, "entries": [{
        "path": "seed.metta", "role": "source_seed", "format": "metta", "portable": False, "reset": False, "owner": "test"}]}), encoding="utf-8")
    patches = [mock.patch.object(metta_server, "ITER_DIR", temp), mock.patch.object(metta_server, "MANIFEST_PATH", manifest_path),
               mock.patch.object(metta_server, "STATE_DIR", temp / ".runtime" / "atomspace"),
               mock.patch.object(metta_server, "WORKING_DIR", temp / ".runtime" / "work")]
    for patch in patches:
        patch.start()
    return metta_server.MettaSpace(), patches


@unittest.skipUnless(os.environ.get("ITERBROW_M15_WORKER") == "1", "M15-D deferred (ITERBROW_M15_WORKER=1 to run)")
@unittest.skipUnless(hyperon_available(), "needs hyperon")
class WarmWorkerTests(unittest.TestCase):
    """M15-D1"""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="m15-worker-"))
        self.space, self.patches = _space(self.temp)
        self.addCleanup(lambda: [p.stop() for p in self.patches])
        self.addCleanup(lambda: getattr(self.space, "shutdown_query_workers", lambda: None)())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp, ignore_errors=True))

    def _tx(self, i, ops):
        return self.space.transact({"transaction_id": "tx-%d" % i, "actor": "t", "source": "u", "operations": ops})

    @pending("M15-D1")
    def test_one_worker_per_view_survives_commits_and_answers_from_the_current_atoms(self):
        require_m15()
        first = self.space.query("!(double 21)", view="current")
        self.assertIn("42", first["result"])
        workers = self.space.status().get("query_workers") or {}
        self.assertIn("current", workers, workers)
        pid = workers["current"]
        self._tx(1, [{"op": "add", "key": "fact:a", "atom": "(fact a 7)"}])
        answer = self.space.query("!(match &self (fact a $v) $v)", view="current")
        self.assertIn("7", answer["result"], "the delta reached the warm worker")
        self.assertEqual((self.space.status().get("query_workers") or {}).get("current"), pid, "the same process answered")
        self._tx(2, [{"op": "replace", "key": "fact:a", "atom": "(fact a 8)"}, {"op": "add", "key": "fact:b", "atom": "(fact b 9)"}])
        answer = self.space.query("!(match &self (fact a $v) $v)", view="current")
        self.assertIn("8", answer["result"])
        self.assertNotIn("7", answer["result"], "the replaced atom is gone from the worker's space")
        self._tx(3, [{"op": "remove", "key": "fact:b"}])
        answer = self.space.query("!(match &self (fact b $v) $v)", view="current")
        self.assertNotIn("9", answer["result"])
        self.assertEqual(answer["view_hash"], self.space.query("!(+ 0 0)", view="current")["view_hash"])
        self.assertEqual(self.space.status().get("query_isolation"), "warm_process_per_view")

    @pending("M15-D1")
    def test_a_dead_or_disagreeing_worker_is_replaced(self):
        require_m15()
        self.space.query("!(double 1)", view="current")
        pid = self.space.status()["query_workers"]["current"]
        import os
        import signal
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
        answer = self.space.query("!(double 2)", view="current")
        self.assertIn("4", answer["result"], "a fresh worker answered")
        self.assertNotEqual(self.space.status()["query_workers"]["current"], pid)
        # Other views keep their own worker; kb and soul views are separate processes.
        self.space.query("!(double 3)", view="kb")
        workers = self.space.status()["query_workers"]
        self.assertNotEqual(workers.get("kb"), workers.get("current"))

    @pending("M15-D1")
    def test_shape(self):
        require_m15()
        src = (ITER_SRC / "metta_server.py").read_text(encoding="utf-8")
        self.assertIn("class QueryWorker", src)
        self.assertIn("def apply(", src)
        self.assertIn("shutdown_query_workers", src)
        worker = (ITER_SRC / "metta_query_worker.py").read_text(encoding="utf-8")
        self.assertIn("--serve", worker)
        self.assertIn('"apply"', worker)
        self.assertIn("def evaluate(", worker, "the one-shot path stays")


@unittest.skipUnless(os.environ.get("ITERBROW_M15_WORKER") == "1", "M15-D deferred (ITERBROW_M15_WORKER=1 to run)")
@unittest.skipUnless(hyperon_available(), "needs hyperon")
class WorkerCostTests(unittest.TestCase):
    """M15-D2"""

    @pending("M15-D2")
    def test_query_after_a_commit_over_20k_atoms_is_fast(self):
        require_m15()
        temp = Path(tempfile.mkdtemp(prefix="m15-workercost-"))
        space, patches = _space(temp)
        self.addCleanup(lambda: [p.stop() for p in patches])
        self.addCleanup(lambda: getattr(space, "shutdown_query_workers", lambda: None)())
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        bulk = [{"op": "add", "key": "event:%05d" % i, "atom": "(event e%d (stv 0.%02d 0.9) \"some text about tool %d\")" % (i, i % 100, i)} for i in range(20000)]
        space.transact({"transaction_id": "bulk", "actor": "t", "source": "u", "operations": bulk})
        space.query("!(double 1)", view="current")  # warms the worker (a full load, once)
        timings = []
        for i in range(5):
            space.transact({"transaction_id": "small-%d" % i, "actor": "t", "source": "u",
                            "operations": [{"op": "upsert", "key": "state:tool_reliability:x", "atom": "(tool-reliability x (stv 0.%d 0.5) %d 1 0)" % (i, i)}]})
            started = time.monotonic()
            answer = space.query("!(match &self (tool-reliability x $stv $c $s $f) $c)", view="current")
            timings.append(time.monotonic() - started)
            self.assertIn(str(i), answer["result"])
        self.assertLess(sorted(timings)[2], 0.15, "median query after a one-atom commit: %s" % timings)


if __name__ == "__main__":
    unittest.main()
