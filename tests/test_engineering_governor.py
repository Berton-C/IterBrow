#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iter"))

from iterbrow_runtime import engineering_governor as governor  # noqa: E402
from iterbrow_runtime.atomspace_store import AtomspaceStore  # noqa: E402
import metta_query_worker  # noqa: E402
from metta_server import _logical_units  # noqa: E402


def work(**changes):
    value = {
        "work_id": "work-1",
        "parent_id": "atlas:COG-GOV-1",
        "intention": "prove native engineering decisions",
        "invariants": "INV-25|INV-26|INV-27",
        "current_state": "durable AtomSpace and PWQ exist",
        "unresolved_gap": "engineering sequence has no native owner",
        "selected_alternative": "native-shadow-governor",
        "counter_alternative": "external-python-policy",
        "predicted_effects": "native commit-bound decision is inspectable",
        "risks": "ambiguous native result",
        "test_obligations": "native rule and restart reconstruction pass",
        "recovery_obligations": "disable evaluation and retain audit atoms",
        "authorization": "pending",
        "authorization_ref": "none",
        "action_status": "pending",
        "observation": "none",
        "test_result": "pending",
        "comparison": "pending",
        "recovery_state": "ready",
        "execution_mode": "shadow",
    }
    value.update(changes)
    return value


class EngineeringGovernorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        nace = (ROOT / "iter" / "seeds" / "nace_substrate.metta").read_text(
            encoding="utf-8"
        )
        engineering = (
            ROOT / "iter" / "seeds" / "engineering_governor.metta"
        ).read_text(
            encoding="utf-8"
        )
        cls.seed = nace + "\n" + engineering
        cls.seed_units = list(_logical_units(cls.seed))

    def native(self, item):
        code = (
            '!(engineering-next "%s")' % item["work_id"]
            if item["execution_mode"] == "active"
            else governor._shadow_query("engineering-shadow-next", item)
        )
        with tempfile.TemporaryDirectory() as temp:
            response = metta_query_worker.evaluate({
                "working_dir": temp,
                "seed_units": self.seed_units,
                "atoms": {
                    "work": governor.work_atom(item),
                    "control": governor.control_atom(item),
                    "metadata": governor.metadata_atom(item),
                },
                "code": code,
            })
        return response

    def native_query(self, atoms, code):
        with tempfile.TemporaryDirectory() as temp:
            return metta_query_worker.evaluate({
                "working_dir": temp,
                "seed_units": self.seed_units,
                "atoms": atoms,
                "code": code,
            })

    def active_work(self, **changes):
        value = work(
            selected_alternative="qa.pwq_board_boundary",
            counter_alternative="keep-shadow-only",
            authorization="authorized",
            authorization_ref=(
                "pwq:pwq-cog-gov-active-action-20260922-a:v2:f6fac657:79bd9fee"
            ),
            execution_mode="active",
        )
        value.update(changes)
        return value

    def raw_observation(self, **changes):
        value = {
            "work_id": "work-1",
            "action_key": "qa.pwq_board_boundary",
            "process_state": "exited",
            "exit_code": 0,
            "stdout_sha256": "a" * 64,
            "stderr_sha256": "b" * 64,
            "output_bytes": 120,
        }
        value.update(changes)
        return value

    def active_native(self, item, observation):
        capsule = governor.context_atom(item, observation)
        atoms = {
            "work": governor.work_atom(item),
            "control": governor.control_atom(item),
            "metadata": governor.metadata_atom(item),
            "context": capsule,
        }
        for index, atom in enumerate(governor.observation_state_atoms(observation).values()):
            atoms["observation-%s" % index] = atom
        return self.native_query(
            atoms,
            governor._context_query("engineering-context-next", capsule),
        )

    def test_work_atom_repeats_selected_alternative_inside_native_shape(self):
        atom = governor.work_atom(work())
        self.assertIn(
            '(alternatives "native-shadow-governor" "external-python-policy")', atom
        )
        self.assertIn('(selected "native-shadow-governor")', atom)
        self.assertIn("(execution-mode shadow)", atom)

    def test_schema_rejects_missing_obligations_and_unauthorized_active_mode(self):
        missing = work()
        del missing["test_obligations"]
        with self.assertRaisesRegex(ValueError, "test_obligations"):
            governor.work_atom(missing)
        with self.assertRaisesRegex(ValueError, "execution_mode"):
            governor.work_atom(work(execution_mode="autonomous"))
        with self.assertRaisesRegex(ValueError, "active work requires authorization"):
            governor.work_atom(work(execution_mode="active"))
        with self.assertRaisesRegex(ValueError, "authorization_ref"):
            governor.work_atom(work(authorization="authorized"))

    def test_native_rule_requests_authorization_from_pending_work(self):
        result = self.native(work())
        self.assertIn(
            '(engineering-decision "work-1" request_authorization '
            '"native-shadow-governor")',
            result,
        )

    def test_authorized_work_is_still_shadow_only(self):
        result = self.native(work(
            authorization="authorized",
            authorization_ref="pwq:proposal-1:digest-1",
        ))
        self.assertIn(
            '(engineering-decision "work-1" shadow_action_ready '
            '"native-shadow-governor")',
            result,
        )
        self.assertNotIn("dispatch", result)

    def test_shadow_ground_control_ignores_heterogeneous_duplicate_work_decoys(self):
        cases = (
            ({}, "request_authorization"),
            ({
                "authorization": "authorized",
                "authorization_ref": "pwq:proposal-1:digest-1",
            }, "shadow_action_ready"),
            ({
                "authorization": "authorized",
                "authorization_ref": "pwq:proposal-1:digest-1",
                "action_status": "completed",
                "observation": "focused tests passed",
                "test_result": "passed",
                "comparison": "matched",
            }, "accept"),
            ({
                "authorization": "authorized",
                "authorization_ref": "pwq:proposal-1:digest-1",
                "action_status": "completed",
                "observation": "prediction was incomplete",
                "test_result": "passed",
                "comparison": "mismatched",
            }, "iterate"),
            ({
                "authorization": "authorized",
                "authorization_ref": "pwq:proposal-1:digest-1",
                "action_status": "completed",
                "observation": "focused tests failed",
                "test_result": "failed",
                "comparison": "mismatched",
            }, "rollback"),
            ({
                "authorization": "authorized",
                "authorization_ref": "pwq:proposal-1:digest-1",
                "action_status": "failed",
                "observation": "recovery point unavailable",
                "test_result": "failed",
                "comparison": "unknown",
                "recovery_state": "unavailable",
            }, "escalate"),
        )
        for changes, expected in cases:
            with self.subTest(expected=expected):
                item = work(**changes)
                decoy = work(
                    **{
                        **changes,
                        "intention": "unrelated semantic-memory projection",
                        "selected_alternative": "neutral",
                        "counter_alternative": "unrelated-counter",
                    }
                )
                result = self.native_query(
                    {
                        "work": governor.work_atom(item),
                        "control": governor.control_atom(item),
                        "metadata": governor.metadata_atom(item),
                        "decoy-work": governor.work_atom(decoy),
                        "decoy-task": (
                            '(task-phase "Consolidation pass 7" complete '
                            '"unrelated string state")'
                        ),
                        "decoy-memory": (
                            '(semantic-memory "work-1" "neutral" observed)'
                        ),
                        "decoy-soul": (
                            '(soul-state 56 "neutral" "flourishing" "proceed")'
                        ),
                    },
                    governor._shadow_query("engineering-shadow-next", item),
                )
                self.assertEqual(
                    governor._DECISION_RE.findall(result),
                    [("work-1", expected, "native-shadow-governor")],
                )

    def test_shadow_next_authenticates_one_exact_ground_control_capsule(self):
        item = work(
            authorization="authorized",
            authorization_ref="pwq:proposal-1:digest-1",
        )
        capsule = governor.control_atom(item)
        result = self.native_query(
            {
                "control": capsule,
                "decoy-control": governor.control_atom(work(
                    authorization="authorized",
                    authorization_ref="pwq:proposal-1:digest-1",
                    selected_alternative="neutral",
                    counter_alternative="unrelated-counter",
                )),
                "decoy-soul": (
                    '(soul-state 56 "neutral" "flourishing" "proceed")'
                ),
            },
            "!(engineering-shadow-next %s)" % capsule,
        )
        self.assertEqual(
            governor._DECISION_RE.findall(result),
            [("work-1", "shadow_action_ready", "native-shadow-governor")],
        )

    def test_authorized_active_work_is_native_dispatch_ready(self):
        result = self.native(self.active_work())
        self.assertIn(
            '(engineering-decision "work-1" active_action_ready '
            '"qa.pwq_board_boundary")',
            result,
        )

    def test_active_ground_control_ignores_unrelated_string_atoms(self):
        item = self.active_work()
        result = self.native_query(
            {
                "work": governor.work_atom(item),
                "control": governor.control_atom(item),
                "metadata": governor.metadata_atom(item),
                "decoy-a": (
                    '(task-phase "Consolidation pass 7" complete '
                    '"unrelated string state")'
                ),
                "decoy-b": (
                    '(task-phase "Consolidation pass 9" complete '
                    '"another unrelated value")'
                ),
            },
            '!(engineering-next "work-1")',
        )
        self.assertIn(
            '(engineering-decision "work-1" active_action_ready '
            '"qa.pwq_board_boundary")',
            result,
        )
        self.assertNotIn("Consolidation pass", result)

    def test_native_active_outcomes_come_from_raw_observation(self):
        cases = (
            ({}, {}, "accept"),
            ({}, {"output_bytes": 0}, "iterate"),
            ({}, {"exit_code": 1}, "rollback"),
            (
                {"recovery_state": "unavailable"},
                {"process_state": "spawn_failed", "exit_code": -1},
                "escalate",
            ),
        )
        for work_changes, observation_changes, expected in cases:
            with self.subTest(expected=expected):
                item = self.active_work(
                    action_status=(
                        "failed"
                        if observation_changes.get("process_state") == "spawn_failed"
                        else "completed"
                    ),
                    observation="raw process evidence",
                    **work_changes,
                )
                result = self.active_native(
                    item, self.raw_observation(**observation_changes)
                )
                self.assertIn(
                    '(engineering-decision "work-1" %s '
                    '"qa.pwq_board_boundary")' % expected,
                    result,
                )

    def test_context_must_exist_exactly_before_native_reasoning(self):
        item = self.active_work(
            action_status="completed", observation="raw process evidence"
        )
        capsule = governor.context_atom(item, self.raw_observation())
        result = self.native_query(
            {"work": governor.work_atom(item)},
            governor._context_query("engineering-context-next", capsule),
        )
        self.assertNotIn("engineering-decision", result)

    def test_ground_context_shields_native_variables_from_heterogeneous_decoys(self):
        item = self.active_work(
            action_status="completed", observation="raw process evidence"
        )
        observation = self.raw_observation(output_bytes=102)
        capsule = governor.context_atom(item, observation)
        result = self.native_query(
            {
                "context": capsule,
                "decoy-a": (
                    '(task-phase "Consolidation pass 7" complete '
                    '"12 hits triaged: unrelated output")'
                ),
                "decoy-b": (
                    '(= (engineering-output-bytes "work-1") '
                    '"unrelated string value")'
                ),
            },
            governor._context_query("engineering-context-tracking", capsule),
        )
        self.assertIn('(engineering-decision "work-1" accept', result)
        self.assertIn("(raw-observation exited 0", result)
        self.assertIn(" 102)", result)
        self.assertNotIn("unrelated", result)

    def test_native_nace_revision_uses_raw_observation(self):
        item = self.active_work(
            action_status="completed", observation="raw process evidence"
        )
        observation = self.raw_observation()
        capsule = governor.context_atom(item, observation)
        result = self.native_query(
            {
                "work": governor.work_atom(item),
                "control": governor.control_atom(item),
                "metadata": governor.metadata_atom(item),
                "context": capsule,
                **{
                    "observation-%s" % index: atom
                    for index, atom in enumerate(
                        governor.observation_state_atoms(observation).values()
                    )
                },
            },
            governor._context_query("engineering-context-evidence", capsule),
        )
        self.assertIn("engineering-evidence-revision", result)
        self.assertIn('"qa.pwq_board_boundary" positive', result)
        self.assertIn("(stv 1.0", result)

    def test_shadow_decision_requires_companion_ground_control_record(self):
        item = work()
        atom = governor.work_atom(item).replace(
            '(selected "native-shadow-governor")',
            '(selected "unconsidered-third-option")',
        )
        result = self.native_query(
            {"work": atom},
            governor._shadow_query("engineering-shadow-next", item),
        )
        self.assertNotIn("engineering-decision", result)

    def test_native_rule_changes_to_rollback_from_failed_evidence(self):
        result = self.native(work(
            authorization="authorized",
            authorization_ref="pwq:proposal-1:digest-1",
            action_status="completed",
            observation="focused native test failed",
            test_result="failed",
            comparison="mismatched",
        ))
        self.assertIn(
            '(engineering-decision "work-1" rollback "native-shadow-governor")',
            result,
        )
        self.assertNotIn("iterate", result)

    def test_native_rule_escalates_when_recovery_is_unavailable(self):
        result = self.native(work(
            authorization="authorized",
            authorization_ref="pwq:proposal-1:digest-1",
            action_status="failed",
            observation="rollback point is missing",
            test_result="failed",
            comparison="unknown",
            recovery_state="unavailable",
        ))
        self.assertIn(
            '(engineering-decision "work-1" escalate "native-shadow-governor")',
            result,
        )

    def test_incomplete_ground_work_capsule_yields_no_tracking_projection(self):
        item = work()
        atom = governor.work_atom(item).replace(
            '(test-obligations "native rule and restart reconstruction pass")',
            '(missing-test-obligations "none")',
        )
        with tempfile.TemporaryDirectory() as temp:
            result = metta_query_worker.evaluate({
                "working_dir": temp,
                "seed_units": self.seed_units,
                "atoms": {
                    "work": atom,
                    "control": governor.control_atom(item),
                },
                "code": governor._shadow_query(
                    "engineering-shadow-tracking", item,
                ),
            })
        self.assertNotIn("tracking", result)

    def test_tracking_is_native_projection_of_work_and_decision(self):
        item = work()
        result = self.native_query(
            {
                "work": governor.work_atom(item),
                "control": governor.control_atom(item),
            },
            governor._shadow_query("engineering-shadow-tracking", item),
        )
        self.assertIn("tracking", result)
        self.assertIn("prove native engineering decisions", result)
        self.assertIn("engineering-decision", result)
        self.assertIn("request_authorization", result)

    def test_journal_replay_reconstructs_same_native_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp) / "atomspace"
            store = AtomspaceStore(state_dir)
            store.transact(
                [
                    {
                        "op": "upsert",
                        "key": "state:engineering_work:work-1",
                        "atom": governor.work_atom(work()),
                    },
                    {
                        "op": "upsert",
                        "key": "state:engineering_control:work-1",
                        "atom": governor.control_atom(work()),
                    },
                ],
                actor="test",
                source="engineering-governor-test",
                transaction_id="work-1-record",
            )
            identity = store.state_copy()
            replayed = AtomspaceStore(state_dir).state_copy()
        self.assertEqual(replayed["epoch"], identity["epoch"])
        self.assertEqual(replayed["commit"], identity["commit"])
        self.assertEqual(replayed["state_hash"], identity["state_hash"])
        code = governor._shadow_query("engineering-shadow-next", work())
        before = self.native_query(identity["atoms"], code)
        after = self.native_query(replayed["atoms"], code)
        self.assertEqual(after, before)
        self.assertIn("request_authorization", after)

    def test_journal_replay_reconstructs_active_outcome_tracking_and_evidence(self):
        item = self.active_work(
            action_status="completed", observation="raw process evidence"
        )
        observation = self.raw_observation()
        observation_atoms = governor.observation_state_atoms(observation)
        capsule = governor.context_atom(item, observation)
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp) / "atomspace"
            store = AtomspaceStore(state_dir)
            store.transact(
                [
                    {
                        "op": "upsert",
                        "key": "state:engineering_work:work-1",
                        "atom": governor.work_atom(item),
                    },
                    {
                        "op": "upsert",
                        "key": "state:engineering_control:work-1",
                        "atom": governor.control_atom(item),
                    },
                    {
                        "op": "upsert",
                        "key": "state:engineering_metadata:work-1",
                        "atom": governor.metadata_atom(item),
                    },
                    {
                        "op": "upsert",
                        "key": "state:engineering_context:work-1",
                        "atom": capsule,
                    },
                    *[
                        {"op": "upsert", "key": "state:%s" % key, "atom": atom}
                        for key, atom in observation_atoms.items()
                    ],
                ],
                actor="test",
                source="engineering-governor-test",
                transaction_id="active-work-1",
            )
            before = store.state_copy()
            replayed = AtomspaceStore(state_dir).state_copy()
        self.assertEqual(replayed["state_hash"], before["state_hash"])
        for function, marker in (
            ("engineering-context-next", "accept"),
            ("engineering-context-tracking", "raw-observation"),
            ("engineering-context-evidence", "positive"),
        ):
            code = governor._context_query(function, capsule)
            first = self.native_query(before["atoms"], code)
            second = self.native_query(replayed["atoms"], code)
            self.assertEqual(second, first)
            self.assertIn(marker, second)

    def test_shadow_adapter_persists_exact_native_decision_and_commit(self):
        evaluated = {
            "ok": True,
            "result": '[(engineering-decision "work-1" rollback "native-shadow-governor")]',
            "epoch": "epoch-7",
            "commit": 41,
            "state_hash": "hash-41",
        }
        commit = mock.Mock(return_value={"commit": 42})
        result = governor.evaluate_shadow(
            "work-1",
            query_fn=mock.Mock(return_value=evaluated),
            commit_fn=commit,
            work_loader_fn=mock.Mock(return_value=work()),
        )
        self.assertEqual(result["decision"], "rollback")
        self.assertFalse(result["dispatch_authority"])
        payload = commit.call_args.kwargs["payload"]
        self.assertEqual(payload["decision"], "rollback")
        self.assertEqual(payload["evaluated_commit"], 41)
        self.assertEqual(payload["evaluated_state_hash"], "hash-41")
        self.assertFalse(payload["dispatch_authority"])

    def test_shadow_adapter_rejects_selected_identity_mismatch_before_commit(self):
        evaluated = {
            "ok": True,
            "result": '[(engineering-decision "work-1" shadow_action_ready "neutral")]',
            "epoch": "epoch-7",
            "commit": 41,
            "state_hash": "hash-41",
        }
        commit = mock.Mock()
        with self.assertRaisesRegex(
            RuntimeError, "selected alternative does not match authoritative work"
        ):
            governor.evaluate_shadow(
                "work-1",
                query_fn=mock.Mock(return_value=evaluated),
                commit_fn=commit,
                work_loader_fn=mock.Mock(return_value=work(
                    authorization="authorized",
                    authorization_ref="pwq:proposal-1:digest-1",
                )),
            )
        commit.assert_not_called()

    def test_recorded_work_loader_stops_at_evaluated_commit(self):
        original = work()
        later = work(selected_alternative="later-choice")
        call = mock.Mock(side_effect=[
            {"commit": 3},
            {"events": [
                {
                    "commit": 1,
                    "metadata": {"domain_events": [{
                        "domain": "engineering_work",
                        "entity_id": "work-1",
                        "event_type": "work_recorded",
                        "payload": {"work": original},
                    }]},
                },
                {
                    "commit": 3,
                    "metadata": {"domain_events": [{
                        "domain": "engineering_work",
                        "entity_id": "work-1",
                        "event_type": "work_recorded",
                        "payload": {"work": later},
                    }]},
                },
            ]},
        ])
        loaded = governor.load_recorded_work(
            "work-1", through_commit=1, call_fn=call,
        )
        self.assertEqual(loaded, original)

    def test_record_work_commits_full_control_and_metadata_atomically(self):
        commit = mock.Mock(return_value={"commit": 7})
        result = governor.record_work(
            self.active_work(),
            transaction_id="active-work-1",
            commit_batch_fn=commit,
        )
        self.assertEqual(result["commit"], 7)
        state = commit.call_args.kwargs["state_atoms"]
        self.assertIn("engineering_work:work-1", state)
        self.assertIn("engineering_control:work-1", state)
        self.assertIn("engineering_metadata:work-1", state)
        self.assertIn('"qa.pwq_board_boundary" authorized pending none', state[
            "engineering_control:work-1"
        ])
        self.assertEqual(commit.call_args.kwargs["transaction_id"], "active-work-1")

    def test_record_active_context_is_ground_versioned_and_idempotent(self):
        item = self.active_work(
            action_status="completed", observation="raw process evidence"
        )
        observation = self.raw_observation()
        commit = mock.Mock(return_value={"commit": 9, "duplicate": False})
        result = governor.record_active_context(
            item, observation, commit_batch_fn=commit,
        )
        self.assertEqual(result["commit"], 9)
        state = commit.call_args.kwargs["state_atoms"]
        self.assertEqual(len(state), 1)
        capsule = next(iter(state.values()))
        self.assertIn("(engineering-context-v1", capsule)
        self.assertIn("(claim", capsule)
        self.assertIn("(observation exited 0", capsule)
        transaction_id = commit.call_args.kwargs["transaction_id"]
        self.assertTrue(transaction_id.startswith("engineering-context:work-1:"))

    def test_ambiguous_native_result_fails_closed_without_decision_commit(self):
        evaluated = {
            "ok": True,
            "result": (
                '[(engineering-decision "work-1" accept "a"), '
                '(engineering-decision "work-1" rollback "a")]'
            ),
            "epoch": "epoch-7", "commit": 41, "state_hash": "hash-41",
        }
        commit = mock.Mock()
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            governor.evaluate_shadow(
                "work-1",
                query_fn=mock.Mock(return_value=evaluated),
                commit_fn=commit,
                work_loader_fn=mock.Mock(return_value=work()),
            )
        commit.assert_not_called()

    def test_active_adapter_refuses_unknown_action_before_query_or_runner(self):
        item = self.active_work(selected_alternative="qa.not_registered")
        query = mock.Mock()
        runner = mock.Mock()
        with self.assertRaisesRegex(ValueError, "unknown governed action"):
            governor.execute_active(
                item,
                {"epoch": "e", "commit": 1, "state_hash": "h"},
                query_fn=query,
                runner_fn=runner,
            )
        query.assert_not_called()
        runner.assert_not_called()

    def test_active_adapter_refuses_stale_snapshot_before_claim_or_runner(self):
        item = self.active_work()
        query = mock.Mock(return_value={
            "ok": True,
            "result": (
                '[(engineering-decision "work-1" active_action_ready '
                '"qa.pwq_board_boundary")]'
            ),
            "epoch": "epoch-1", "commit": 8, "state_hash": "hash-8",
        })
        commit = mock.Mock()
        runner = mock.Mock()
        with self.assertRaisesRegex(RuntimeError, "snapshot is stale"):
            governor.execute_active(
                item,
                {"epoch": "epoch-1", "commit": 7, "state_hash": "hash-7"},
                query_fn=query,
                commit_fn=commit,
                runner_fn=runner,
            )
        commit.assert_not_called()
        runner.assert_not_called()

    def test_active_dispatch_claim_is_idempotent_and_never_reruns(self):
        item = self.active_work()
        query = mock.Mock(return_value={
            "ok": True,
            "result": (
                '[(engineering-decision "work-1" active_action_ready '
                '"qa.pwq_board_boundary")]'
            ),
            "epoch": "epoch-1", "commit": 7, "state_hash": "hash-7",
        })
        runner = mock.Mock()
        result = governor.execute_active(
            item,
            {"epoch": "epoch-1", "commit": 7, "state_hash": "hash-7"},
            query_fn=query,
            commit_fn=mock.Mock(return_value={"commit": 8, "duplicate": True}),
            runner_fn=runner,
        )
        self.assertEqual(result["status"], "already_claimed")
        self.assertFalse(result["dispatched"])
        runner.assert_not_called()

    def test_fixed_action_uses_exact_argv_without_shell(self):
        completed = CompletedProcess([], 0, b"ok", b"")
        with mock.patch.object(
            governor.subprocess, "run", return_value=completed
        ) as run:
            result = governor._run_fixed_action("qa.pwq_board_boundary")
        self.assertEqual(result.returncode, 0)
        args, kwargs = run.call_args
        self.assertEqual(tuple(args[0]), governor.ACTION_REGISTRY["qa.pwq_board_boundary"])
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["cwd"], str(ROOT))

    def test_active_adapter_records_raw_observation_and_native_results(self):
        item = self.active_work()
        query = mock.Mock(side_effect=[
            {
                "ok": True,
                "result": (
                    '[(engineering-decision "work-1" active_action_ready '
                    '"qa.pwq_board_boundary")]'
                ),
                "epoch": "epoch-1", "commit": 7, "state_hash": "hash-7",
            },
            {
                "ok": True,
                "result": (
                    '[(engineering-decision "work-1" accept '
                    '"qa.pwq_board_boundary")]'
                ),
                "epoch": "epoch-1", "commit": 9, "state_hash": "hash-9",
            },
            {
                "ok": True,
                "result": (
                    '[(engineering-evidence-revision "work-1" '
                    '"qa.pwq_board_boundary" positive (stv 1.0 0.3333333333))]'
                ),
                "epoch": "epoch-1", "commit": 10, "state_hash": "hash-10",
            },
        ])
        commit = mock.Mock(side_effect=[
            {"commit": 8, "duplicate": False},
            {"commit": 10, "duplicate": False},
            {"commit": 11, "duplicate": False},
        ])
        commit_batch = mock.Mock(return_value={"commit": 9, "duplicate": False})
        runner = mock.Mock(return_value=CompletedProcess(
            [], 0, b"Ran 4 tests\nOK\n", b""
        ))
        result = governor.execute_active(
            item,
            {"epoch": "epoch-1", "commit": 7, "state_hash": "hash-7"},
            query_fn=query,
            commit_fn=commit,
            commit_batch_fn=commit_batch,
            runner_fn=runner,
        )
        self.assertEqual(result["decision"], "accept")
        self.assertEqual(result["evidence_revision"]["label"], "positive")
        self.assertFalse(result["python_semantic_classification"])
        self.assertEqual(result["observation"]["exit_code"], 0)
        payload = commit_batch.call_args.args[0][0]["payload"]
        self.assertEqual(payload["action_key"], "qa.pwq_board_boundary")
        self.assertEqual(payload["output_bytes"], len(b"Ran 4 tests\nOK\n"))
        work_state = commit_batch.call_args.kwargs["state_atoms"][
            "engineering_work:work-1"
        ]
        self.assertIn("(test-result pending)", work_state)
        self.assertIn("(comparison pending)", work_state)
        state_atoms = commit_batch.call_args.kwargs["state_atoms"]
        context_keys = [
            key for key in state_atoms if key.startswith("engineering_context:")
        ]
        self.assertEqual(len(context_keys), 1)
        self.assertIn("(engineering-context-v1", state_atoms[context_keys[0]])

    def test_recovery_is_read_only_native_reconstruction(self):
        query = mock.Mock(return_value={
            "ok": True,
            "result": (
                '[(tracking "work-1" "intent" "gap" '
                '"qa.pwq_board_boundary" (raw-observation exited 0 "a" "b" 10) '
                'matched (engineering-decision "work-1" accept '
                '"qa.pwq_board_boundary") '
                '(engineering-evidence-revision "work-1" '
                '"qa.pwq_board_boundary" positive (stv 1.0 0.3333333333)))]'
            ),
            "epoch": "epoch-1", "commit": 11, "state_hash": "hash-11",
        })
        recovered = governor.recover_active(
            "work-1", query_fn=query,
            work=self.active_work(), observation=self.raw_observation(),
        )
        self.assertEqual(recovered["decision"], "accept")
        self.assertEqual(recovered["evidence_revision"]["label"], "positive")
        self.assertFalse(recovered["dispatched"])
        self.assertEqual(recovered["authority"], "atomspace_reconstruction")
        self.assertEqual(query.call_count, 1)

    def test_recovery_rehydrates_context_from_authoritative_events(self):
        item = self.active_work()
        observation = self.raw_observation()
        call = mock.Mock(side_effect=[
            {"commit": 2},
            {"events": [
                {
                    "commit": 1,
                    "metadata": {"domain_events": [{
                        "domain": "engineering_work",
                        "entity_id": "work-1",
                        "event_type": "work_recorded",
                        "payload": {"work": item},
                    }]},
                },
                {
                    "commit": 2,
                    "metadata": {"domain_events": [{
                        "domain": "engineering_observation",
                        "entity_id": "work-1",
                        "event_type": "raw_process_observed",
                        "payload": observation,
                    }]},
                },
            ]},
        ])
        loaded_work, loaded_observation = governor.load_active_context(
            "work-1", call_fn=call,
        )
        self.assertEqual(loaded_work, item)
        self.assertEqual(loaded_observation, observation)
        self.assertEqual(call.call_args_list[1].args, ("subscribe",))


if __name__ == "__main__":
    unittest.main()
