"""Shared cognitive-event transactions for legacy store migration.

Domain code commits authoritative event/state atoms first, then updates its
existing file as a compatibility projection or index. A failed authoritative
commit raises and the projection must not advance.
"""

import hashlib
import json
import os
import socket
import time
import uuid


SOCKET_PATH = os.environ.get("ITER_METTA_SOCKET", "/tmp/iter-metta-bridge.sock")


def metta_string(value):
    return json.dumps(str(value), ensure_ascii=False)


def _call_atomspace(method, timeout=30, **params):
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    deadline = time.monotonic() + timeout

    def remaining():
        budget = deadline - time.monotonic()
        if budget <= 0:
            raise socket.timeout("AtomSpace request deadline exceeded")
        connection.settimeout(budget)

    try:
        remaining()
        connection.connect(SOCKET_PATH)
        request = json.dumps({"method": method, "params": params}, ensure_ascii=False) + "\n"
        remaining()
        connection.sendall(request.encode("utf-8"))
        buffer = b""
        while b"\n" not in buffer:
            remaining()
            chunk = connection.recv(1 << 20)
            if not chunk:
                break
            buffer += chunk
        if b"\n" not in buffer:
            raise ConnectionError("AtomSpace closed without a full response")
        response = json.loads(buffer.partition(b"\n")[0].decode("utf-8"))
        if not response.get("ok"):
            raise RuntimeError(response.get("error") or "AtomSpace transaction failed")
        return response.get("result")
    finally:
        connection.close()


def _event_atom(event):
    payload_hash = hashlib.sha256(
        json.dumps(event.get("payload") or {}, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return "(cognitive-event %s %s %s %s %s)" % (
        metta_string(event["event_id"]),
        metta_string(event["domain"]),
        metta_string(event["event_type"]),
        metta_string(event["entity_id"]),
        metta_string(payload_hash),
    )


def commit_batch(events, state_atoms=None, remove_state_keys=None, actor="iter",
                 source="cognition", transaction_id=None, timeout=30, expected_atoms=None):
    normalised = []
    operations = []
    for raw in events or []:
        event = dict(raw)
        event.setdefault("event_id", str(uuid.uuid4()))
        for required in ("domain", "entity_id", "event_type"):
            if not event.get(required):
                raise ValueError("cognitive event requires %s" % required)
        event.setdefault("payload", {})
        normalised.append(event)
        operations.append({
            "op": "add",
            "key": "event:%s" % event["event_id"],
            "atom": _event_atom(event),
        })
    for key, atom in (state_atoms or {}).items():
        operations.append({"op": "upsert", "key": "state:%s" % key, "atom": atom})
    for key in remove_state_keys or []:
        operations.append({"op": "remove", "key": "state:%s" % key})
    if not operations:
        raise ValueError("cognitive transaction has no operations")
    if transaction_id is None:
        transaction_id = "cognitive:%s" % uuid.uuid4()
    try:
        return _call_atomspace(
            "transact",
            timeout=timeout,
            operations=operations,
            actor=actor,
            source=source,
            transaction_id=transaction_id,
            metadata={"domain_events": normalised},
            **({"expected_atoms": expected_atoms} if expected_atoms is not None else {}),
        )
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout, OSError) as exc:
        # Electron sets ITER_REQUIRE_ATOMSPACE=1 for the real runtime, making
        # cognitive writes fail closed if authority is unavailable. Direct
        # offline unit/maintenance invocations retain legacy compatibility and
        # report that the authoritative event was not committed.
        if os.environ.get("ITER_REQUIRE_ATOMSPACE") == "1":
            raise
        return {"deferred": True, "reason": "%s: %s" % (type(exc).__name__, exc)}


def commit_event(domain, entity_id, event_type, payload=None, state_atom=None,
                 actor="iter", source="cognition", event_id=None,
                 transaction_id=None, timeout=30):
    event = {
        "event_id": event_id or str(uuid.uuid4()),
        "domain": domain,
        "entity_id": entity_id,
        "event_type": event_type,
        "payload": payload or {},
    }
    state_atoms = {"%s:%s" % (domain, entity_id): state_atom} if state_atom else None
    return commit_batch(
        [event], state_atoms=state_atoms, actor=actor, source=source,
        transaction_id=transaction_id or ("cognitive:%s" % event["event_id"]),
        timeout=timeout,
    )
