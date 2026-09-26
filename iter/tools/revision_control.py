"""Agent client for quarantined, human-authorized runtime revisions."""

import json
import os
import sys
from pathlib import Path


ROOT = Path(os.getenv("ITER_DIR", Path.cwd())).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from iterbrow_runtime.hotload_manager import HotloadManager


MANAGER = HotloadManager(ROOT)
DESCRIPTION = (
    "Stage and validate complete immutable tool/transformation/channel revisions. "
    "Stage leaves code inert; activate starts ordinary self-repair without creating "
    "a PWQ card. When acting on an explicit PWQ item, supply its proposal_id; "
    "its existing approval and scope are checked. Activation enters externally supervised "
    "probation; the candidate cannot promote itself. Actions: status, stage, "
    "validate, activate, rollback_probation."
)


def _json_value(value, label):
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError("%s is required" % label)
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        try:
            candidate = Path(text)
            if candidate.is_file():
                return json.loads(candidate.read_text(encoding="utf-8"))
        except OSError:
            pass
        raise ValueError("%s must be valid JSON or a readable JSON file" % label) from error


def run(action="status", candidate_id="", changes="", contract="",
        proposal_id="", dispatch_authorization="", required_heartbeats="3",
        heartbeat_timeout="720", reason="agent requested safe rollback"):
    try:
        action = str(action or "status").strip().lower()
        if action == "status":
            result = MANAGER.status()
        elif action == "stage":
            result = MANAGER.stage(
                _json_value(changes, "changes"),
                _json_value(contract, "contract"),
            )
        elif action == "validate":
            result = MANAGER.validate(candidate_id)
        elif action == "activate":
            if proposal_id and not dispatch_authorization:
                work = MANAGER.approved_revision_work(
                    MANAGER._read_candidate(candidate_id), proposal_id)
                proposal_id = work["id"]
                dispatch_authorization = work["dispatch_authorization"]
            result = MANAGER.activate(
                candidate_id, proposal_id, dispatch_authorization,
                required_heartbeats=int(required_heartbeats or 3),
                heartbeat_timeout=float(heartbeat_timeout or 720),
            )
        elif action in ("rollback", "rollback_probation"):
            result = MANAGER.rollback_probation(reason)
        else:
            raise ValueError("unknown revision action: %s" % action)
        return json.dumps(result, sort_keys=True, default=str)
    except Exception as exc:
        return json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)})
