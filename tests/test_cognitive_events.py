#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iter"))

from iterbrow_runtime import cognitive_events  # noqa: E402


class CognitiveEventTests(unittest.TestCase):
    def test_event_and_state_share_one_transaction(self):
        with mock.patch.object(cognitive_events, "_call_atomspace", return_value={"commit": 7}) as call:
            result = cognitive_events.commit_event(
                "task", "atlas", "phase_set", {"phase": "building"},
                state_atom='(task-phase "atlas" building "")',
                event_id="evt-1", transaction_id="tx-1",
            )
        self.assertEqual(result["commit"], 7)
        params = call.call_args.kwargs
        self.assertEqual(params["transaction_id"], "tx-1")
        self.assertEqual(len(params["operations"]), 2)
        self.assertEqual(params["operations"][0]["key"], "event:evt-1")
        self.assertEqual(params["operations"][1]["key"], "state:task:atlas")
        self.assertEqual(params["metadata"]["domain_events"][0]["payload"]["phase"], "building")

    def test_batch_can_remove_projected_state(self):
        with mock.patch.object(cognitive_events, "_call_atomspace", return_value={"commit": 8}) as call:
            cognitive_events.commit_batch(
                [{"event_id": "evt-2", "domain": "memory", "entity_id": "m1", "event_type": "forgotten"}],
                remove_state_keys=["memory:m1"], transaction_id="tx-2",
            )
        operations = call.call_args.kwargs["operations"]
        self.assertEqual(operations[-1], {"op": "remove", "key": "state:memory:m1"})


if __name__ == "__main__":
    unittest.main()
