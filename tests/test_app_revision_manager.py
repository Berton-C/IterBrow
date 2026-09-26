#!/usr/bin/env python3
import os
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT / "iter") not in sys.path:
    sys.path.insert(0, str(ROOT / "iter"))

from iterbrow_runtime.app_revision_manager import (  # noqa: E402
    AppRevisionError,
    AppRevisionManager,
)
from iterbrow_runtime.pwq_protocol import PWQStore  # noqa: E402


BASE = """<!doctype html><html><body><main>base</main><script>
const api = window.iterApp;
api.appContext().then(() => document.body.dataset.iterReady = 'true');
</script></body></html>\n"""
GOOD = BASE.replace("base", "candidate")


class AppRevisionManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.iter_root = Path(self.temporary.name) / "iter"
        (self.iter_root / "crm").mkdir(parents=True)
        (self.iter_root / "crm" / "index.html").write_text(BASE, encoding="utf-8")
        self.store = PWQStore(
            self.iter_root / ".runtime" / "pwq",
            self.iter_root / ".runtime" / "pwq.json",
        )
        self.manager = AppRevisionManager(self.iter_root, pwq_store=self.store)
        self.base = self.manager.ensure_baseline("crm")

    def tearDown(self):
        self.temporary.cleanup()

    def contract(self, files=None):
        files = files or ["index.html"]
        return {
            "version": "2",
            "purpose": "bounded application repair",
            "source_pressure": "acceptance evidence",
            "atlas_slice": "APP-2",
            "entrypoint": "index.html",
            "allowed_files": files,
            "tests": [
                "bundle_integrity",
                "entrypoint_contract",
                "network_membrane",
            ],
            "rollback_target": self.base["revision_id"],
            "provenance": "unit-test",
        }

    def validated(self, content=GOOD):
        candidate = self.manager.stage(
            "crm", {"index.html": content}, self.contract()
        )
        candidate = self.manager.validate(candidate["candidate_id"])
        self.assertTrue(candidate["validation"]["passed"])
        self.assertFalse(candidate["validation"]["candidate_executed"])
        return candidate

    def authorize(self, candidate, proposal_id="app-revision-test"):
        self.store.command(
            "propose", proposal_id, actor="iter",
            payload={
                "title": "Activate CRM application revision",
                "ask": "Approve bounded probation",
                "work_class": "build",
                "governance_refs": {
                    "atlas_slices": ["APP-2", "REC-1"],
                    "invariants": ["INV-15", "INV-21", "INV-32", "INV-33"],
                },
                "approval_policy": self.manager.split_approval_policy(),
                "authorization_scope": self.manager.candidate_authorization_scope(candidate),
            },
        )
        witnessed = self.manager.attest_candidate(candidate["candidate_id"], proposal_id)
        item = next(entry for entry in witnessed["items"] if entry["id"] == proposal_id)
        self.assertFalse(item["approval_status"]["ready"])
        approved = self.store.command(
            "approve", proposal_id, actor="human", expected_version=1,
        )
        item = next(entry for entry in approved["items"] if entry["id"] == proposal_id)
        self.assertTrue(item["approval_status"]["ready"])
        return proposal_id, item["dispatch_authorization"]

    def test_stage_is_content_addressed_immutable_and_inert(self):
        candidate = self.manager.stage(
            "crm", {"index.html": GOOD}, self.contract()
        )
        self.assertEqual(candidate["status"], "quarantined")
        self.assertTrue(candidate["revision_id"].startswith("apprev-"))
        self.assertEqual(
            self.manager.status("crm")["active"]["revision_id"],
            self.base["revision_id"],
        )
        bundle = Path(candidate["bundle_path"])
        self.assertEqual((bundle / "index.html").read_text(encoding="utf-8"), GOOD)
        self.assertFalse(candidate.get("authorization"))
        with self.assertRaises(FileExistsError):
            (bundle / "index.html").open("x", encoding="utf-8")

    def test_scope_traversal_unexpected_files_and_network_code_fail_closed(self):
        with self.assertRaisesRegex(AppRevisionError, "supported application"):
            self.manager.stage("other", {"index.html": GOOD}, self.contract())
        with self.assertRaisesRegex(AppRevisionError, "traverse"):
            self.manager.stage("crm", {"../index.html": GOOD}, self.contract())
        with self.assertRaisesRegex(AppRevisionError, "allowed_files"):
            self.manager.stage(
                "crm", {"index.html": GOOD, "extra.js": "const x = 1;"},
                self.contract(),
            )
        bad = self.manager.stage(
            "crm",
            {"index.html": GOOD.replace("</script>", "fetch('https://example.com');</script>")},
            self.contract(),
        )
        checked = self.manager.validate(bad["candidate_id"])
        self.assertEqual(checked["status"], "validation_failed")
        self.assertFalse(checked["validation"]["passed"])
        self.assertFalse(checked["validation"]["candidate_executed"])

    def test_validation_rejects_missing_app_contract_without_execution(self):
        broken = self.manager.stage(
            "crm", {"index.html": "<!doctype html><html><body>broken</body></html>"},
            self.contract(),
        )
        checked = self.manager.validate(broken["candidate_id"])
        self.assertEqual(checked["status"], "validation_failed")
        self.assertFalse(checked["validation"]["candidate_executed"])
        self.assertIn("entrypoint_contract", {
            result["test"] for result in checked["validation"]["results"]
            if not result["passed"]
        })

    def test_activation_requires_exact_candidate_authorization(self):
        candidate = self.validated()
        proposal_id, token = self.authorize(candidate)
        with self.assertRaisesRegex(AppRevisionError, "dispatch authorization"):
            self.manager.activate(candidate["candidate_id"], proposal_id, "wrong")
        pointer = self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_observations=2, observation_timeout=60,
        )
        self.assertEqual(pointer["status"], "probation")
        self.assertEqual(pointer["previous_revision_id"], self.base["revision_id"])
        self.assertEqual(pointer["revision_id"], candidate["revision_id"])

    def test_only_distinct_external_load_and_context_proofs_promote(self):
        candidate = self.validated()
        proposal_id, token = self.authorize(candidate)
        self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_observations=2, observation_timeout=60,
        )
        first = self.manager.supervisor_report(
            "crm", candidate["revision_id"], "proof-1",
            load_ok=True, visible_handshake=True, context_ok=True,
            context_commit=7,
        )
        self.assertEqual(first["action"], "waiting")
        duplicate = self.manager.supervisor_report(
            "crm", candidate["revision_id"], "proof-1",
            load_ok=True, visible_handshake=True, context_ok=True,
            context_commit=7,
        )
        self.assertEqual(duplicate["action"], "waiting")
        promoted = self.manager.supervisor_report(
            "crm", candidate["revision_id"], "proof-2",
            load_ok=True, visible_handshake=True, context_ok=True,
            context_commit=7,
        )
        self.assertEqual(promoted["action"], "promoted")
        self.assertEqual(self.manager.status("crm")["active"]["status"], "stable")
        item = next(entry for entry in self.store.read()["items"] if entry["id"] == proposal_id)
        self.assertEqual(item["tracking"]["atlas_slice"], "APP-2")
        self.assertEqual(item["tracking"]["sequence"], 5)
        self.assertIn("All 2", item["tracking"]["evidence_open_gaps"])

    def test_failed_health_timeout_and_startup_recover_exact_parent(self):
        candidate = self.validated()
        proposal_id, token = self.authorize(candidate)
        active = self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_observations=1, observation_timeout=30,
        )
        failed = self.manager.supervisor_report(
            "crm", candidate["revision_id"], "failed-load",
            load_ok=False, visible_handshake=False, context_ok=False,
            detail="renderer load failed",
        )
        self.assertEqual(failed["action"], "rolled_back")
        self.assertEqual(failed["active"]["revision_id"], self.base["revision_id"])
        failed_item = next(
            entry for entry in self.store.read()["items"] if entry["id"] == proposal_id
        )
        self.assertEqual(failed_item["status"], "paused")
        self.assertEqual(failed_item["tracking"]["atlas_slice"], "REC-1")
        self.assertIn("rollback completed", failed_item["tracking"]["evidence_open_gaps"])

        second = self.validated(GOOD.replace("candidate", "candidate-two"))
        proposal_id, token = self.authorize(second, "app-revision-timeout")
        active = self.manager.activate(
            second["candidate_id"], proposal_id, token,
            required_observations=1, observation_timeout=30,
        )
        timed_out = self.manager.supervisor_check(
            "crm", renderer_present=True, now=active["activated_at"] + 31,
        )
        self.assertEqual(timed_out["action"], "rolled_back")
        self.assertEqual(timed_out["active"]["revision_id"], self.base["revision_id"])

        third = self.validated(GOOD.replace("candidate", "candidate-three"))
        proposal_id, token = self.authorize(third, "app-revision-startup")
        self.manager.activate(third["candidate_id"], proposal_id, token)
        recovered = self.manager.recover_on_startup("crm")
        self.assertEqual(recovered["action"], "rolled_back")
        self.assertEqual(recovered["active"]["revision_id"], self.base["revision_id"])

    def test_tamper_blocks_activation_and_rolls_back_promoted_revision(self):
        candidate = self.validated()
        proposal_id, token = self.authorize(candidate)
        Path(candidate["bundle_path"], "index.html").write_text(
            GOOD + "<!--tampered-->", encoding="utf-8"
        )
        with self.assertRaisesRegex(AppRevisionError, "hash"):
            self.manager.activate(candidate["candidate_id"], proposal_id, token)

        fresh = self.validated(GOOD.replace("candidate", "stable-new"))
        proposal_id, token = self.authorize(fresh, "app-revision-stable")
        self.manager.activate(
            fresh["candidate_id"], proposal_id, token,
            required_observations=1,
        )
        promoted = self.manager.supervisor_report(
            "crm", fresh["revision_id"], "healthy",
            load_ok=True, visible_handshake=True, context_ok=True,
            context_commit=8,
        )
        self.assertEqual(promoted["action"], "promoted")
        Path(fresh["bundle_path"], "index.html").write_text(
            GOOD + "<!--corrupt-after-promotion-->", encoding="utf-8"
        )
        recovered = self.manager.recover_on_startup("crm")
        self.assertEqual(recovered["action"], "rolled_back")
        self.assertEqual(recovered["active"]["revision_id"], self.base["revision_id"])

    def test_incomplete_final_event_write_is_repaired_before_next_append(self):
        with self.manager.events_path.open("ab") as handle:
            handle.write(b'{"interrupted":')
        candidate = self.manager.stage(
            "crm", {"index.html": GOOD}, self.contract()
        )
        self.assertEqual(candidate["status"], "quarantined")
        events = [
            json.loads(line)
            for line in self.manager.events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        kinds = [event["kind"] for event in events]
        self.assertIn("ledger_tail_recovered", kinds)
        self.assertEqual(kinds[-1], "candidate_staged")


if __name__ == "__main__":
    unittest.main()
