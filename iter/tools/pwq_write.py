"""Canonical narrow-command PWQ protocol client.

The agent may never synchronize a caller-supplied board projection. Historic
whole-board admission is available only through this module's explicit offline
migration entry point; normal runtime calls use one version-bound command.
"""

import json
import os
import sys
from pathlib import Path


ROOT = Path(os.environ.get("ITER_DIR") or Path.cwd()).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from iterbrow_runtime.pwq_protocol import PWQStore


STORE = PWQStore(ROOT / ".runtime" / "pwq", ROOT / ".runtime" / "pwq.json")

DESCRIPTION = (
    "Agent client for the canonical PWQ human-agency protocol. Iter may propose, "
    "modify/counter-propose, read, start approved work with the current "
    "dispatch_authorization, append a scope-bound Tracking update, pause, or complete. "
    "Tracking is optional progress reporting, not permission to build; it cannot "
    "change consent or scope. Atlas labels are optional. Approve/reject/reorder are "
    "human-only decisions and this tool cannot mint them. command_id makes a "
    "retry idempotent. The event ledger is authoritative; .runtime/pwq.json is "
    "a read-only projection."
)


def _normalise_kwargs(kwargs):
    if "kwargs" in kwargs and isinstance(kwargs["kwargs"], str):
        return json.loads(kwargs["kwargs"])
    return kwargs


def run(action="read", proposal_id="", payload=None, expected_version=None,
        command_id="", **kwargs):
    try:
        supplied = _normalise_kwargs(kwargs)
        action = supplied.get("action", action)
        proposal_id = supplied.get("proposal_id", proposal_id)
        payload = supplied.get("payload", payload)
        expected_version = supplied.get("expected_version", expected_version)
        command_id = supplied.get("command_id", command_id)
        actor = "iter"
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as error:
                try:
                    payload = json.loads(Path(payload).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    raise ValueError("payload must be valid JSON or a readable JSON file") from error

        action = str(action or "read").lower()
        if action == "read":
            result = STORE.read()
        elif action in ("write", "sync"):
            raise ValueError("write/sync is reserved for explicit offline migration")
        elif action == "propose":
            if not isinstance(payload, dict):
                raise ValueError("propose requires a proposal payload")
            proposal_id = proposal_id or payload.get("id")
            result = STORE.command(
                "propose", proposal_id, actor=actor, payload=payload,
                command_id=command_id or None,
            )
        else:
            result = STORE.command(
                action, proposal_id, actor=actor, payload=payload or {},
                expected_version=expected_version,
                command_id=command_id or None,
            )
        return json.dumps(result, sort_keys=True)
    except Exception as exc:
        return json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: pwq_write.py <payload.json>")
        raise SystemExit(1)
    board = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(STORE.sync_board(board, actor="migration"))
