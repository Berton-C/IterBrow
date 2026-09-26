#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iter"))

from iterbrow_runtime.atomspace_store import (  # noqa: E402
    AtomspaceStore,
    AtomspaceStoreError,
    TransactionConflict,
)


class FakeEngine:
    def __init__(self):
        self.states = []

    def rebuild(self, atoms):
        self.states.append(dict(atoms))


class AtomspaceStoreTests(unittest.TestCase):
    def make_store(self, directory, snapshot_every=50):
        return AtomspaceStore(Path(directory) / "atomspace", snapshot_every=snapshot_every)

    def test_commit_replays_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = FakeEngine()
            store = self.make_store(temp)
            first = store.transact(
                [{"op": "add", "key": "belief:one", "atom": "(belief one)"}],
                actor="test",
                source="unit",
                transaction_id="tx-1",
                rebuild_engine=engine.rebuild,
            )
            duplicate = store.transact(
                [{"op": "add", "key": "belief:one", "atom": "(belief one)"}],
                transaction_id="tx-1",
                rebuild_engine=engine.rebuild,
            )
            self.assertEqual(first["commit"], 1)
            self.assertTrue(duplicate["duplicate"])
            self.assertEqual(len(engine.states), 1)

            recovered = self.make_store(temp)
            self.assertEqual(recovered.commit, 1)
            self.assertEqual(recovered.atoms, {"belief:one": "(belief one)"})
            again = recovered.transact(
                [{"op": "add", "key": "belief:one", "atom": "(belief one)"}],
                transaction_id="tx-1",
            )
            self.assertTrue(again["duplicate"])

    def test_replace_remove_and_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.transact([{"op": "add", "key": "k", "atom": "(value old)"}], transaction_id="a")
            store.transact([{"op": "replace", "key": "k", "atom": "(value new)"}], transaction_id="b")
            self.assertEqual(store.atoms["k"], "(value new)")
            store.transact([{"op": "remove", "key": "k"}], transaction_id="c")
            self.assertNotIn("k", store.atoms)
            with self.assertRaises(TransactionConflict):
                store.transact([{"op": "replace", "key": "missing", "atom": "(x)"}])
            store.transact([{"op": "upsert", "key": "new", "atom": "(new one)"}], transaction_id="d")
            store.transact([{"op": "upsert", "key": "new", "atom": "(new two)"}], transaction_id="e")
            self.assertEqual(store.atoms["new"], "(new two)")

    def test_uncommitted_prepare_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            prepare = {
                "schema_version": 1,
                "kind": "prepare",
                "epoch": store.epoch,
                "transaction_id": "interrupted",
                "commit": 1,
                "actor": "test",
                "source": "unit",
                "at": 1,
                "operations": [{"op": "add", "key": "ghost", "atom": "(ghost)"}],
                "metadata": {},
                "previous_state_hash": store.state_hash,
                "next_state_hash": "unused",
            }
            with store.wal_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(prepare) + "\n")
            recovered = self.make_store(temp)
            self.assertEqual(recovered.commit, 0)
            self.assertNotIn("ghost", recovered.atoms)

    def test_incomplete_final_journal_write_is_repaired_before_next_append(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.transact(
                [{"op": "add", "key": "first", "atom": "(first durable)"}],
                transaction_id="first-tx",
            )
            with store.wal_path.open("ab") as handle:
                handle.write(b'{"schema_version":1,"kind":"commit"')

            recovered = self.make_store(temp)
            self.assertEqual(recovered.commit, 1)
            self.assertEqual(recovered.atoms["first"], "(first durable)")
            recovered.transact(
                [{"op": "add", "key": "second", "atom": "(second durable)"}],
                transaction_id="second-tx",
            )

            replayed = self.make_store(temp)
            self.assertEqual(replayed.commit, 2)
            self.assertEqual(
                replayed.atoms,
                {"first": "(first durable)", "second": "(second durable)"},
            )
            records = [
                json.loads(line)
                for line in replayed.wal_path.read_text(encoding="utf-8").splitlines()
            ]
            recovery = next(record for record in records if record.get("kind") == "recovery")
            self.assertEqual(recovery["epoch"], replayed.epoch)
            self.assertIn("discarded_tail_sha256", recovery)

    def test_complete_malformed_journal_record_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            with store.wal_path.open("ab") as handle:
                handle.write(b'{"broken":\n')
            with self.assertRaises(AtomspaceStoreError):
                self.make_store(temp)

    def test_engine_failure_aborts_without_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            calls = []

            def fail_then_restore(atoms):
                calls.append(dict(atoms))
                if "bad" in atoms:
                    raise RuntimeError("engine refused atom")

            with self.assertRaises(RuntimeError):
                store.transact(
                    [{"op": "add", "key": "bad", "atom": "(bad)"}],
                    transaction_id="bad-tx",
                    rebuild_engine=fail_then_restore,
                )
            self.assertEqual(store.commit, 0)
            self.assertEqual(store.atoms, {})
            self.assertEqual(calls[-1], {})
            recovered = self.make_store(temp)
            self.assertEqual(recovered.atoms, {})

    def test_quiesce_checkpoint_subscribe_and_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = FakeEngine()
            store = self.make_store(temp, snapshot_every=1)
            store.transact(
                [{"op": "add", "key": "k", "atom": "(v)"}],
                transaction_id="tx",
                actor="iter",
                source="task",
                metadata={"domain": "task"},
                rebuild_engine=engine.rebuild,
            )
            events = store.events_after(0)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["metadata"]["domain"], "task")
            store.set_quiesced(True)
            with self.assertRaises(AtomspaceStoreError):
                store.transact([{"op": "add", "key": "blocked", "atom": "(blocked)"}])
            store.set_quiesced(False)
            old_epoch = store.epoch
            reset = store.reset(rebuild_engine=engine.rebuild)
            self.assertNotEqual(reset["epoch"], old_epoch)
            self.assertEqual(store.atoms, {})
            self.assertEqual(store.commit, 0)
            self.assertEqual(self.make_store(temp).atoms, {})


if __name__ == "__main__":
    unittest.main()
