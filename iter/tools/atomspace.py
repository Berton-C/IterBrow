"""Structured durable access to IterBrow's authoritative AtomSpace."""

import json
import sys
from pathlib import Path


_TOOLS = str(Path(__file__).resolve().parent)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from _metta_bridge import call


DESCRIPTION = (
    "Query or durably mutate IterBrow's authoritative AtomSpace. "
    "Actions: status; query(code); add(atom, key?); replace/upsert(key, atom); "
    "remove(key); transact(operations_json, transaction_id?); checkpoint. "
    "Mutations are journaled, idempotent when transaction_id is reused, and "
    "survive service restart."
)


def _decode_operations(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        decoded = json.loads(value)
        if isinstance(decoded, list):
            return decoded
    raise ValueError("operations must be a JSON array")


def run(action="status", atom="", key="", code="", operations_json="",
        transaction_id="", source="tools.atomspace"):
    action = str(action).strip().lower()
    try:
        if action == "status":
            result = call("status", timeout=5)
        elif action == "query":
            result = call("query", timeout=30, code=code)
        elif action in ("add", "replace", "upsert"):
            operation = {"op": action, "atom": atom}
            if key:
                operation["key"] = key
            result = call(
                "transact", timeout=30,
                operations=[operation], actor="iter", source=source,
                transaction_id=transaction_id or None,
                metadata={"domain": "direct_atomspace_tool"},
            )
        elif action == "remove":
            result = call(
                "transact", timeout=30,
                operations=[{"op": "remove", "key": key}],
                actor="iter", source=source,
                transaction_id=transaction_id or None,
                metadata={"domain": "direct_atomspace_tool"},
            )
        elif action == "transact":
            result = call(
                "transact", timeout=30,
                operations=_decode_operations(operations_json),
                actor="iter", source=source,
                transaction_id=transaction_id or None,
                metadata={"domain": "direct_atomspace_tool"},
            )
        elif action == "checkpoint":
            result = call("checkpoint", timeout=30)
        else:
            return json.dumps({"error": "unknown action: %s" % action})
        return json.dumps(result, sort_keys=True)
    except Exception as exc:
        return json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)})
