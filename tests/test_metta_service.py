#!/usr/bin/env python3
import concurrent.futures
import json
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iter"))

import metta_server  # noqa: E402
import metta_query_worker  # noqa: E402


class FakeEnvironment:
    @staticmethod
    def custom_env(**_kwargs):
        return object()


class FakeMeTTa:
    instances = []

    def __init__(self, env_builder=None):
        self.atoms = []
        self.calls = []
        self.__class__.instances.append(self)

    def run(self, code):
        self.calls.append(code)
        marker = "!(add-atom &self "
        if code.startswith(marker) and code.endswith(")"):
            self.atoms.append(code[len(marker):-1])
        return ["ok"]

    def parse_all(self, code):
        self.calls.append(("parse", code))
        return [code]

    def space(self):
        return self

    def add_atom(self, atom):
        self.calls.append(("add", atom))
        self.atoms.append(atom)


class ThreadSensitiveMeTTa(FakeMeTTa):
    activity_lock = threading.Lock()
    active_calls = 0
    maximum_active_calls = 0

    def add_atom(self, atom):
        with self.activity_lock:
            type(self).active_calls += 1
            type(self).maximum_active_calls = max(
                type(self).maximum_active_calls,
                type(self).active_calls,
            )
        try:
            time.sleep(0.005)
            return super().add_atom(atom)
        finally:
            with self.activity_lock:
                type(self).active_calls -= 1

    def run(self, code):
        with self.activity_lock:
            type(self).active_calls += 1
            type(self).maximum_active_calls = max(
                type(self).maximum_active_calls,
                type(self).active_calls,
            )
        try:
            time.sleep(0.005)
            return super().run(code)
        finally:
            with self.activity_lock:
                type(self).active_calls -= 1


class MettaServiceTests(unittest.TestCase):
    def test_optional_governed_seeds_cannot_break_existing_reasoner_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / 'legacy.metta').write_text('(legacy available)')
            (root / 'broken_optional.metta').write_text('(unbalanced')
            manifest = {'schema_version': 1, 'entries': [
                {'path': 'legacy.metta', 'role': 'source_seed', 'format': 'metta'},
                {'path': 'broken_optional.metta', 'role': 'source_seed', 'format': 'metta_governed'},
                {'path': 'absent_optional.metta', 'role': 'source_seed', 'format': 'metta_governed'}]}
            path = root / 'state_manifest.json'
            path.write_text(json.dumps(manifest))
            with mock.patch.object(metta_server, 'ITER_DIR', root), mock.patch.object(metta_server, 'MANIFEST_PATH', path):
                seeds = metta_server._load_declared_seeds()
            self.assertEqual([seed['path'] for seed in seeds], ['legacy.metta'])
            self.assertEqual(seeds[0]['units'], ['(legacy available)'])

    def test_raw_mutation_preserves_memory_but_cannot_forge_platform_fabric(self):
        from iterbrow_runtime.atomspace_store import AtomspaceStore
        with tempfile.TemporaryDirectory() as temp:
            space = metta_server.MettaSpace.__new__(metta_server.MettaSpace)
            space.store = AtomspaceStore(Path(temp))
            space.engine = object()
            space._rebuild_engine = lambda _atoms: None
            normal = {'operations': [{'op': 'add', 'key': 'state:semantic_memory:existing',
                                      'atom': '(memory "still available")'}]}
            space.transact(normal)
            with self.assertRaises(PermissionError):
                space.transact({'operations': [{'op': 'upsert', 'key': 'fabric:atom:control:active-governance',
                                                'atom': '(forged approval)'}]})
            self.assertIn('state:semantic_memory:existing', space.store.atoms)
            self.assertEqual(space.store.commit, 1)

    def test_reserved_namespace_is_checked_after_key_normalization_for_every_operation(self):
        from iterbrow_runtime.atomspace_store import AtomspaceStore
        with tempfile.TemporaryDirectory() as temp:
            space = metta_server.MettaSpace.__new__(metta_server.MettaSpace)
            space.store = AtomspaceStore(Path(temp))
            space.engine = object()
            space._rebuild_engine = lambda _atoms: None
            # Trusted internal service state exists; generic clients must not
            # create, replace or remove it through alternate raw spellings.
            reserved = 'fabric:atom:control:active-governance'
            space.store.transact([{'op': 'add', 'key': reserved, 'atom': '(trusted receipt)'}])
            before = space.store.state_copy()
            for spelling in (reserved, ' ' + reserved, reserved + ' ', '\t\n' + reserved + '\r\n',
                             '\u00a0' + reserved + '\u00a0'):
                for operation in ('add', 'replace', 'upsert', 'remove'):
                    with self.subTest(spelling=repr(spelling), operation=operation):
                        proposed = {'op': operation, 'key': spelling}
                        if operation != 'remove':
                            proposed['atom'] = '(forged receipt)'
                        with self.assertRaises(PermissionError):
                            space.transact({'operations': [
                                {'op': 'upsert', 'key': 'state:semantic_memory:not-partially-written',
                                 'atom': '(uncommitted memory)'}, proposed]})
                        self.assertEqual(space.store.state_copy(), before)

    def test_normalized_default_memory_keys_and_implicit_atom_keys_still_work(self):
        from iterbrow_runtime.atomspace_store import AtomspaceStore
        with tempfile.TemporaryDirectory() as temp:
            space = metta_server.MettaSpace.__new__(metta_server.MettaSpace)
            space.store = AtomspaceStore(Path(temp))
            space.engine = object()
            space._rebuild_engine = lambda _atoms: None
            space.transact({'operations': [
                {'op': 'add', 'key': '  state:semantic_memory:existing \n', 'atom': ' (memory original) '},
                {'op': 'add', 'atom': ' (legacy implicit key) '}]})
            self.assertEqual(space.store.atoms['state:semantic_memory:existing'], '(memory original)')
            self.assertTrue(any(key.startswith('sha256:') and atom == '(legacy implicit key)'
                                for key, atom in space.store.atoms.items()))
            space.transact({'operations': [{'op': 'replace', 'key': '\tstate:semantic_memory:existing ',
                                            'atom': '(memory updated)'}]})
            self.assertEqual(space.store.atoms['state:semantic_memory:existing'], '(memory updated)')
            space.transact({'operations': [{'op': 'remove', 'key': ' state:semantic_memory:existing\t'}]})
            self.assertNotIn('state:semantic_memory:existing', space.store.atoms)

    def test_query_worker_loads_program_before_durable_atoms_then_evaluates(self):
        fake_hyperon = types.SimpleNamespace(MeTTa=FakeMeTTa, Environment=FakeEnvironment)
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.dict(sys.modules, {"hyperon": fake_hyperon}):
            result = metta_query_worker.evaluate({
                "working_dir": temp,
                "seed_units": ["(= (seed-rule) seeded)"],
                "atoms": {"durable": "(durable fact)"},
                "code": "(= (temporary-rule) temporary)\n!(temporary-rule)",
            })
        calls = FakeMeTTa.instances[-1].calls
        self.assertEqual(calls, [
            ("parse", "(= (seed-rule) seeded)"),
            ("add", "(= (seed-rule) seeded)"),
            "(= (temporary-rule) temporary)",
            ("parse", "(durable fact)"),
            ("add", "(durable fact)"),
            "!(temporary-rule)",
        ])
        self.assertEqual(result, "['ok']")

    def test_singleton_lock_is_exclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            lock_path = Path(temp) / "service.lock"
            with mock.patch.object(metta_server, "LOCK_PATH", str(lock_path)):
                first = metta_server._acquire_singleton_lock()
                self.assertIsNotNone(first)
                try:
                    self.assertIsNone(metta_server._acquire_singleton_lock())
                finally:
                    first.close()

    def test_singleton_lock_bootstraps_a_fresh_state_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            lock_path = Path(temp) / ".runtime" / "atomspace" / "service.lock"
            self.assertFalse(lock_path.parent.exists())
            with mock.patch.object(metta_server, "LOCK_PATH", str(lock_path)):
                handle = metta_server._acquire_singleton_lock()
                self.assertIsNotNone(handle)
                try:
                    self.assertTrue(lock_path.is_file())
                    self.assertEqual(lock_path.read_text(encoding="utf-8"), str(metta_server.os.getpid()))
                finally:
                    handle.close()

    def test_declared_seeds_only_durable_rebuild_and_query_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp).resolve()
            (temp_path / "seed.metta").write_text("(declared seed)\n", encoding="utf-8")
            (temp_path / "rogue.metta").write_text("(rogue runtime)\n", encoding="utf-8")
            manifest = {
                "schema_version": 1,
                "entries": [{
                    "path": "seed.metta", "role": "source_seed", "format": "metta",
                    "portable": False, "reset": False, "owner": "test",
                }],
            }
            manifest_path = temp_path / "state_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            fake_hyperon = types.SimpleNamespace(MeTTa=FakeMeTTa, Environment=FakeEnvironment)
            with mock.patch.dict(sys.modules, {"hyperon": fake_hyperon}), \
                 mock.patch.object(metta_server, "ITER_DIR", temp_path), \
                 mock.patch.object(metta_server, "MANIFEST_PATH", manifest_path), \
                 mock.patch.object(metta_server, "STATE_DIR", temp_path / ".runtime" / "atomspace"), \
                 mock.patch.object(metta_server, "WORKING_DIR", temp_path / ".runtime" / "work"):
                space = metta_server.MettaSpace()
                self.assertTrue(space.engine_available)
                self.assertEqual(space.status()["seed_files"], ["seed.metta"])
                self.assertEqual(space.status()["state_dir"], str(temp_path / ".runtime" / "atomspace"))
                self.assertIn("(declared seed)", space.engine.atoms)
                self.assertNotIn("(rogue runtime)", space.engine.atoms)

                before_engine = space.engine
                with mock.patch.object(
                    space, "_run_query_worker", return_value="[[temporary result]]"
                ) as isolated_query:
                    query = space.query("!(add-atom &self (temporary query fact))")
                self.assertEqual(query["commit"], 0)
                self.assertEqual(query["result"], "[[temporary result]]")
                self.assertEqual(isolated_query.call_args.args[0]["atoms"], {})
                self.assertIs(space.engine, before_engine)
                self.assertNotIn("(temporary query fact)", space.engine.atoms)

                committed = space.transact({
                    "transaction_id": "tx-service",
                    "actor": "test",
                    "source": "unit",
                    "operations": [{"op": "add", "key": "fact:durable", "atom": "(durable fact)"}],
                })
                self.assertEqual(committed["commit"], 1)
                self.assertIn("(durable fact)", space.engine.atoms)

                recovered = metta_server.MettaSpace()
                self.assertEqual(recovered.status()["commit"], 1)
                self.assertIn("(durable fact)", recovered.engine.atoms)

    def test_native_hyperon_entry_is_serialized_across_rebuilds(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp).resolve()
            (temp_path / "seed.metta").write_text("(declared seed)\n", encoding="utf-8")
            manifest_path = temp_path / "state_manifest.json"
            manifest_path.write_text(json.dumps({
                "schema_version": 1,
                "entries": [{
                    "path": "seed.metta", "role": "source_seed", "format": "metta",
                    "portable": False, "reset": False, "owner": "test",
                }],
            }), encoding="utf-8")
            fake_hyperon = types.SimpleNamespace(
                MeTTa=ThreadSensitiveMeTTa,
                Environment=FakeEnvironment,
            )
            ThreadSensitiveMeTTa.active_calls = 0
            ThreadSensitiveMeTTa.maximum_active_calls = 0
            with mock.patch.dict(sys.modules, {"hyperon": fake_hyperon}), \
                 mock.patch.object(metta_server, "ITER_DIR", temp_path), \
                 mock.patch.object(metta_server, "MANIFEST_PATH", manifest_path), \
                 mock.patch.object(metta_server, "STATE_DIR", temp_path / ".runtime" / "atomspace"), \
                 mock.patch.object(metta_server, "WORKING_DIR", temp_path / ".runtime" / "work"):
                space = metta_server.MettaSpace()
                ThreadSensitiveMeTTa.maximum_active_calls = 0
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                    work = [pool.submit(space._new_engine, {}) for _ in range(12)]
                    work.extend(
                        pool.submit(space.transact, {
                            "transaction_id": "concurrent-%d" % index,
                            "actor": "test",
                            "source": "concurrency-regression",
                            "operations": [{
                                "op": "add",
                                "key": "fact:%d" % index,
                                "atom": "(fact %d)" % index,
                            }],
                        })
                        for index in range(4)
                    )
                    for future in work:
                        future.result(timeout=10)
                self.assertEqual(ThreadSensitiveMeTTa.maximum_active_calls, 1)
                self.assertEqual(space.status()["commit"], 4)


if __name__ == "__main__":
    unittest.main()
