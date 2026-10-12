#!/usr/bin/env python3
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "iter" / "state_manifest.json"


class StateManifestTests(unittest.TestCase):
    def test_manifest_has_one_entry_per_path_and_valid_roles(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        entries = data["entries"]
        paths = [entry["path"] for entry in entries]
        self.assertEqual(len(paths), len(set(paths)))
        valid = {
            "source_seed", "authoritative_state", "event_log", "projection",
            "projection_index", "cache", "secret", "application_state",
            "legacy_queue", "legacy_log",
        }
        for entry in entries:
            self.assertIn(entry["role"], valid)
            self.assertIsInstance(entry["portable"], bool)
            self.assertIsInstance(entry["reset"], bool)
            self.assertTrue(entry["owner"])

    def test_declared_source_seeds_exist(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for entry in data["entries"]:
            if entry["role"] == "source_seed":
                self.assertTrue((ROOT / "iter" / entry["path"]).is_file(), entry["path"])

    def test_secrets_are_not_portable(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for entry in data["entries"]:
            if entry["role"] == "secret":
                self.assertFalse(entry["portable"], entry["path"])

    def test_known_credential_containers_are_secrets(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        by_path = {entry["path"]: entry for entry in data["entries"]}
        for path in (".runtime/settings.json", "private"):
            self.assertEqual(by_path[path]["role"], "secret")
            self.assertFalse(by_path[path]["portable"])

    def test_chat_receipts_are_portable_state_but_delivery_queues_are_not(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        by_path = {entry["path"]: entry for entry in data["entries"]}
        journal = by_path[".runtime/electron_ui/messages.jsonl"]
        self.assertEqual(journal["role"], "application_state")
        self.assertTrue(journal["portable"])
        self.assertTrue(journal["reset"])  # Factory Reset clears the visible chat with Iter's memory
        for name in ("inbox", "outbox", "staging", "recovery"):
            queue = by_path[".runtime/electron_ui/" + name]
            self.assertFalse(queue["portable"])
            self.assertTrue(queue["reset"])


    def test_reset_never_deletes_and_restore_never_replaces_tracked_source(self):
        import subprocess
        try:
            tracked = subprocess.run(["git", "ls-files", "iter"], cwd=str(MANIFEST.parents[1]),
                                     capture_output=True, text=True, check=True).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for entry in data["entries"]:
            prefix = "iter/" + entry["path"].rstrip("/")
            covered = [t for t in tracked if t == prefix or t.startswith(prefix + "/")]
            if not covered or entry["role"] == "source_seed":
                continue
            self.assertFalse(entry["reset"], "Reset would delete tracked source %s" % covered[:3])
            if entry["portable"]:
                self.assertTrue(entry.get("merge_on_restore"),
                                "Import would replace tracked source %s; set merge_on_restore" % covered[:3])

    def test_source_seeds_are_never_reset(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for entry in data["entries"]:
            if entry["role"] == "source_seed":
                self.assertFalse(entry["reset"], entry["path"])


    def test_user_data_survives_factory_reset(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        by_path = {entry["path"]: entry for entry in data["entries"]}
        for path in ("crm/data", "uploads", "apps", ".runtime/settings.json", "private",
                     ".runtime/tabs_session.json", ".runtime/hotload"):
            self.assertFalse(by_path[path]["reset"], path)


if __name__ == "__main__":
    unittest.main()
