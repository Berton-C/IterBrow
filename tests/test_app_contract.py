#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iter"))

from iterbrow_runtime import app_contract  # noqa: E402
from iterbrow_runtime.atomspace_store import AtomspaceStore  # noqa: E402


class AtomspaceHarness:
    def __init__(self, state_dir):
        self.store = AtomspaceStore(state_dir)
        self.subscribe_calls = 0

    def call(self, method, **params):
        if method == "status":
            state = self.store.state_copy()
            return {
                "epoch": state["epoch"],
                "commit": state["commit"],
                "state_hash": state["state_hash"],
            }
        if method == "subscribe":
            self.subscribe_calls += 1
            return {
                "epoch": self.store.epoch,
                "events": self.store.events_after(
                    params.get("after_commit", 0), params.get("limit", 1000)
                ),
                "current_commit": self.store.commit,
            }
        raise AssertionError("unexpected method: %s" % method)

    def commit_batch(self, events, state_atoms=None, remove_state_keys=None,
                     actor="iter", source="application_contract",
                     transaction_id=None):
        operations = []
        for event in events:
            operations.append({
                "op": "add",
                "key": "event:%s" % event["event_id"],
                "atom": '(test-application-event "%s")' % event["event_id"],
            })
        for key, atom in (state_atoms or {}).items():
            operations.append({"op": "upsert", "key": "state:%s" % key, "atom": atom})
        for key in remove_state_keys or []:
            operations.append({"op": "remove", "key": "state:%s" % key})
        return self.store.transact(
            operations,
            actor=actor,
            source=source,
            transaction_id=transaction_id,
            metadata={"domain_events": events},
        )


def provenance(source="crm-ui"):
    return {"type": "observed", "source": source, "actor": "human"}


def command(command_id, command_type, expected_revision, **payload):
    return {
        "command_id": command_id,
        "type": command_type,
        "expected_revision": expected_revision,
        "provenance": provenance(),
        **payload,
    }


class ApplicationContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp.name) / "atomspace"
        self.harness = AtomspaceHarness(self.state_dir)

    def tearDown(self):
        self.temp.cleanup()

    def apply(self, value, consumer="crm-ui"):
        return app_contract.apply_command(
            "crm", consumer, value,
            call_fn=self.harness.call,
            commit_batch_fn=self.harness.commit_batch,
        )

    def context(self):
        return app_contract.read_context("crm", call_fn=self.harness.call)

    def test_zero_one_many_records_are_commit_identified(self):
        empty = self.context()
        self.assertEqual(empty["revision"], 0)
        self.assertEqual(empty["records"], {})
        self.assertIn("commit", empty)

        first = self.apply(command(
            "create-c1", "create", 0,
            collection="contacts", record={"id": "c1", "name": "Ada"},
        ))
        second = self.apply(command(
            "create-c2", "create", 1,
            collection="contacts", record={"id": "c2", "name": "Grace"},
        ))
        self.assertEqual(first["revision"], 1)
        self.assertEqual(second["revision"], 2)
        self.assertLess(first["commit"], second["commit"])
        current = self.context()
        self.assertEqual(
            [item["id"] for item in current["records"]["contacts"]],
            ["c1", "c2"],
        )
        self.assertEqual(current["commit"], second["commit"])

    def test_duplicate_command_is_idempotent_and_collision_fails(self):
        original = command(
            "create-c1", "create", 0,
            collection="contacts", record={"id": "c1", "name": "Ada"},
        )
        first = self.apply(original)
        replay = self.apply(original)
        self.assertTrue(replay["duplicate"])
        self.assertEqual(replay["commit"], first["commit"])
        self.assertEqual(self.context()["revision"], 1)

        conflicting = command(
            "create-c1", "create", 1,
            collection="contacts", record={"id": "c1", "name": "Changed"},
        )
        with self.assertRaisesRegex(ValueError, "command_id.*different payload"):
            self.apply(conflicting)
        self.assertEqual(self.context()["revision"], 1)

    def test_stale_revision_and_invalid_provenance_fail_before_commit(self):
        self.apply(command(
            "create-c1", "create", 0,
            collection="contacts", record={"id": "c1", "name": "Ada"},
        ))
        before = self.harness.store.state_copy()
        with self.assertRaisesRegex(app_contract.StaleRevision, "expected 0.*current 1"):
            self.apply(command(
                "create-c2", "create", 0,
                collection="contacts", record={"id": "c2", "name": "Grace"},
            ))
        invalid = command(
            "create-c3", "create", 1,
            collection="contacts", record={"id": "c3", "name": "Lin"},
        )
        invalid["provenance"] = {"type": "observed"}
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.apply(invalid)
        after = self.harness.store.state_copy()
        self.assertEqual(after["commit"], before["commit"])
        self.assertEqual(after["state_hash"], before["state_hash"])

    def test_replace_delete_and_undo_are_replayable_corrections(self):
        self.apply(command(
            "create-c1", "create", 0,
            collection="contacts", record={"id": "c1", "name": "Ada"},
        ))
        self.apply(command(
            "replace-c1", "replace", 1,
            collection="contacts", record={"id": "c1", "name": "Ada Lovelace"},
        ))
        restored = self.apply(command(
            "undo-replace-c1", "undo", 2, target_command_id="replace-c1",
        ))
        self.assertEqual(restored["record"]["name"], "Ada")
        self.apply(command(
            "delete-c1", "delete", 3, collection="contacts", record_id="c1",
        ))
        self.assertEqual(self.context()["records"].get("contacts", []), [])
        undeleted = self.apply(command(
            "undo-delete-c1", "undo", 4, target_command_id="delete-c1",
        ))
        self.assertEqual(undeleted["record"], {"id": "c1", "name": "Ada"})

        replayed = AtomspaceHarness(self.state_dir)
        replay_context = app_contract.read_context("crm", call_fn=replayed.call)
        self.assertEqual(replay_context["revision"], 5)
        self.assertEqual(replay_context["records"]["contacts"], [{"id": "c1", "name": "Ada"}])

    def test_import_is_atomic_idempotent_and_native_fields_are_materialized(self):
        value = command(
            "crm-bootstrap-v1", "import", 0,
            collections={
                "contacts": [{"id": "c1", "name": "Ada", "tags": ["math"]}],
                "tasks": [{"id": "t1", "title": "Follow up"}],
                "events": [],
                "captures": [],
            },
        )
        result = self.apply(value, consumer="platform.migration")
        replay = self.apply(value, consumer="platform.migration")
        self.assertEqual(result["revision"], 1)
        self.assertTrue(replay["duplicate"])
        atoms = self.harness.store.state_copy()["atoms"]
        self.assertIn("state:application_record:crm:contacts:c1", atoms)
        self.assertIn("state:application_field:crm:contacts:c1:name", atoms)
        self.assertIn('"observed"', atoms["state:application_record:crm:contacts:c1"])
        self.assertIn('"Ada"', atoms["state:application_field:crm:contacts:c1:name"])

    def test_changes_are_filtered_and_projection_rebuilds_from_authority(self):
        first = self.apply(command(
            "create-c1", "create", 0,
            collection="contacts", record={"id": "c1", "name": "Ada"},
        ))
        self.apply(command(
            "create-t1", "create", 1,
            collection="tasks", record={"id": "t1", "title": "Follow up"},
        ))
        changes = app_contract.read_changes(
            "crm", first["commit"], call_fn=self.harness.call,
        )
        self.assertEqual(len(changes["events"]), 1)
        self.assertEqual(changes["events"][0]["command_id"], "create-t1")

        projection = Path(self.temp.name) / "crm-data"
        projection.mkdir()
        for collection in app_contract.CRM_COLLECTIONS:
            (projection / (collection + ".json")).write_text("BROKEN", encoding="utf-8")
        rebuilt = app_contract.rebuild_json_projection(
            "crm", projection, call_fn=self.harness.call,
        )
        self.assertEqual(rebuilt["revision"], 2)
        self.assertEqual(
            json.loads((projection / "contacts.json").read_text(encoding="utf-8")),
            [{"id": "c1", "name": "Ada"}],
        )
        self.assertEqual(
            json.loads((projection / "tasks.json").read_text(encoding="utf-8")),
            [{"id": "t1", "title": "Follow up"}],
        )
        self.assertEqual(
            json.loads((projection / "events.json").read_text(encoding="utf-8")), []
        )

    def test_second_consumer_is_isolated_by_application_scope(self):
        fixture_command = command(
            "create-shared-id", "create", 0,
            collection="notes", record={"id": "n1", "text": "fixture"},
        )
        fixture = app_contract.apply_command(
            "contract-fixture", "contract-fixture", fixture_command,
            call_fn=self.harness.call,
            commit_batch_fn=self.harness.commit_batch,
        )
        self.assertEqual(fixture["revision"], 1)
        self.assertEqual(self.context()["records"], {})
        fixture_context = app_contract.read_context(
            "contract-fixture", call_fn=self.harness.call,
        )
        self.assertEqual(
            fixture_context["records"]["notes"],
            [{"id": "n1", "text": "fixture"}],
        )

        # Command ids and revisions are scoped to an application: using the
        # same id in CRM is a distinct transaction, not a false duplicate.
        crm_result = self.apply(command(
            "create-shared-id", "create", 0,
            collection="notes", record={"id": "n1", "text": "crm"},
        ))
        self.assertFalse(crm_result["duplicate"])
        self.assertEqual(self.context()["records"]["notes"][0]["text"], "crm")

    def test_projection_failure_is_reported_without_reclassifying_authority(self):
        with mock.patch.object(
            app_contract, "rebuild_json_projection",
            side_effect=OSError("projection unavailable"),
        ):
            status = app_contract._projection_status(
                "crm", Path(self.temp.name) / "projection",
            )
        self.assertFalse(status["ok"])
        self.assertIn("projection unavailable", status["error"])

    def test_replay_cache_is_disposable_and_catches_up_from_authority(self):
        self.apply(command(
            "create-c1", "create", 0,
            collection="contacts", record={"id": "c1", "name": "Ada"},
        ))
        cache_root = Path(self.temp.name) / "service-root"
        self.harness.subscribe_calls = 0
        first, first_cache = app_contract._load_service_state(
            cache_root, "crm", call_fn=self.harness.call,
        )
        self.assertTrue(first_cache["ok"])
        self.assertGreater(self.harness.subscribe_calls, 0)
        self.assertEqual(first["records"]["contacts"]["c1"]["name"], "Ada")

        self.harness.subscribe_calls = 0
        second, second_cache = app_contract._load_service_state(
            cache_root, "crm", call_fn=self.harness.call,
        )
        self.assertTrue(second_cache["ok"])
        self.assertEqual(self.harness.subscribe_calls, 0)
        self.assertEqual(second["commit"], first["commit"])

        self.apply(command(
            "create-c2", "create", 1,
            collection="contacts", record={"id": "c2", "name": "Grace"},
        ))
        self.harness.subscribe_calls = 0
        caught_up, _ = app_contract._load_service_state(
            cache_root, "crm", call_fn=self.harness.call,
        )
        self.assertGreater(self.harness.subscribe_calls, 0)
        self.assertEqual(caught_up["revision"], 2)

        cache_path = app_contract._cache_path(cache_root, "crm")
        cache_path.write_text("corrupt", encoding="utf-8")
        self.harness.subscribe_calls = 0
        rebuilt, _ = app_contract._load_service_state(
            cache_root, "crm", call_fn=self.harness.call,
        )
        self.assertGreater(self.harness.subscribe_calls, 0)
        self.assertEqual(rebuilt["records"], caught_up["records"])

        self.harness.store.reset()
        after_reset, _ = app_contract._load_service_state(
            cache_root, "crm", call_fn=self.harness.call,
        )
        self.assertNotEqual(after_reset["epoch"], rebuilt["epoch"])
        self.assertEqual(after_reset["revision"], 0)
        self.assertEqual(after_reset["records"], {})


if __name__ == "__main__":
    unittest.main()
