#!/usr/bin/env python3
"""Journaled AtomSpace-backed collaboration contract for IterBrow tab/apps.

The AtomSpace domain event is authoritative. JSON files are optional rebuildable
projections. Commands are typed, idempotent, provenance-bearing, and guarded by
one application revision. The service boundary at the bottom of this module is
used directly so packaged builds include it through ``iterbrow_runtime/**/*``.
"""

import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iterbrow_runtime.cognitive_events import (  # noqa: E402
    _call_atomspace,
    commit_batch,
    metta_string,
)


DOMAIN = "application_contract"
CACHE_SCHEMA = 1
CRM_COLLECTIONS = ("contacts", "tasks", "events", "captures")
COMMAND_TYPES = {"create", "replace", "delete", "undo", "import"}
PROVENANCE_TYPES = {"observed", "reported", "inferred", "imported"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class StaleRevision(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_copy(value, label):
    try:
        return json.loads(_canonical(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("%s must be JSON-serializable" % label) from exc


def _identifier(value, label):
    value = str(value or "").strip()
    if not IDENTIFIER.fullmatch(value):
        raise ValueError("%s is invalid" % label)
    return value


def _provenance(value):
    if not isinstance(value, dict):
        raise ValueError("provenance must be an object")
    result = {
        "type": str(value.get("type", "")).strip().lower(),
        "source": str(value.get("source", "")).strip(),
        "actor": str(value.get("actor", "")).strip(),
    }
    if result["type"] not in PROVENANCE_TYPES:
        raise ValueError("provenance type is invalid")
    if not result["source"] or not result["actor"]:
        raise ValueError("provenance requires source and actor")
    return result


def _record(value, label="record"):
    if not isinstance(value, dict):
        raise ValueError("%s must be an object" % label)
    result = _json_copy(value, label)
    result["id"] = _identifier(result.get("id"), "%s id" % label)
    for field in result:
        _identifier(field, "%s field" % label)
    return result


def _normalise_command(value):
    if not isinstance(value, dict):
        raise ValueError("application command must be an object")
    command_type = str(value.get("type", "")).strip().lower()
    if command_type not in COMMAND_TYPES:
        raise ValueError("application command type is invalid")
    try:
        expected_revision = int(value["expected_revision"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("application command requires expected_revision") from exc
    if expected_revision < 0:
        raise ValueError("expected_revision cannot be negative")
    result = {
        "command_id": _identifier(value.get("command_id"), "command_id"),
        "type": command_type,
        "expected_revision": expected_revision,
        "provenance": _provenance(value.get("provenance")),
    }
    if command_type in {"create", "replace"}:
        result["collection"] = _identifier(value.get("collection"), "collection")
        result["record"] = _record(value.get("record"))
    elif command_type == "delete":
        result["collection"] = _identifier(value.get("collection"), "collection")
        result["record_id"] = _identifier(value.get("record_id"), "record_id")
    elif command_type == "undo":
        result["target_command_id"] = _identifier(
            value.get("target_command_id"), "target_command_id"
        )
        if result["target_command_id"] == result["command_id"]:
            raise ValueError("undo cannot target itself")
    else:
        collections = value.get("collections")
        if not isinstance(collections, dict):
            raise ValueError("import requires collections")
        normalised = {}
        for raw_collection, raw_records in collections.items():
            collection = _identifier(raw_collection, "collection")
            if not isinstance(raw_records, list):
                raise ValueError("import collection must be an array")
            records = [_record(item, "import record") for item in raw_records]
            ids = [item["id"] for item in records]
            if len(ids) != len(set(ids)):
                raise ValueError("import collection contains duplicate record ids")
            normalised[collection] = records
        result["collections"] = normalised
    return result


def _state_key(app_id, collection, record_id):
    return "application_record:%s:%s:%s" % (app_id, collection, record_id)


def _field_key(app_id, collection, record_id, field):
    return "application_field:%s:%s:%s:%s" % (
        app_id, collection, record_id, field,
    )


def _record_atom(app_id, collection, record, revision, provenance, command_id):
    return " ".join((
        "(application-record", metta_string(app_id), metta_string(collection),
        metta_string(record["id"]), str(int(revision)), "active",
        metta_string(_canonical(record)),
        "(provenance", metta_string(provenance["type"]),
        metta_string(provenance["source"]), metta_string(provenance["actor"]),
        metta_string(command_id), "))",
    ))


def _field_atom(app_id, collection, record_id, field, value, revision):
    # Keep scalar strings directly legible to native MeTTa rules while using
    # canonical JSON for every other JSON value. The full record atom remains
    # the lossless source for reconstruction; field atoms are query indexes.
    encoded_value = value if isinstance(value, str) else _canonical(value)
    return " ".join((
        "(application-field", metta_string(app_id), metta_string(collection),
        metta_string(record_id), metta_string(field),
        metta_string(encoded_value), str(int(revision)), ")",
    ))


def _domain_transactions(call_fn, after_commit=0, through_commit=None):
    status = call_fn("status")
    current_commit = int((status or {}).get("commit", 0))
    if through_commit is not None:
        through_commit = int(through_commit)
        if through_commit > current_commit:
            raise RuntimeError("requested application snapshot is in the future")
        current_commit = through_commit
    after = int(after_commit or 0)
    transactions = []
    while after < current_commit:
        page = call_fn("subscribe", after_commit=after, limit=1000)
        batch = list((page or {}).get("events") or [])
        if not batch:
            break
        for transaction in batch:
            if int(transaction.get("commit", 0)) <= current_commit:
                transactions.append(transaction)
        next_after = max(int(item.get("commit", 0)) for item in batch)
        if next_after <= after:
            break
        after = next_after
    if after < current_commit:
        raise RuntimeError(
            "authoritative subscription stopped at commit %d before %d"
            % (after, current_commit)
        )
    return status, transactions


def _load_state(app_id, call_fn=_call_atomspace, through_commit=None,
                initial_state=None):
    app_id = _identifier(app_id, "app_id")
    base = None
    if isinstance(initial_state, dict) and initial_state.get("app_id") == app_id:
        base = _json_copy(initial_state, "initial application state")
    after_commit = int((base or {}).get("commit", 0))
    status, transactions = _domain_transactions(
        call_fn, after_commit=after_commit, through_commit=through_commit,
    )
    target_commit = int(status.get("commit", 0) if through_commit is None else through_commit)
    if base and (
        base.get("epoch") != status.get("epoch")
        or after_commit > target_commit
        or (
            after_commit == target_commit
            and base.get("state_hash") != status.get("state_hash")
        )
    ):
        base = None
        status, transactions = _domain_transactions(
            call_fn, through_commit=through_commit,
        )
    records = (base or {}).get("records") or {}
    receipts = (base or {}).get("receipts") or {}
    revision = int((base or {}).get("revision", 0))
    for transaction in transactions:
        commit = int(transaction.get("commit", 0))
        for event in (transaction.get("metadata") or {}).get("domain_events", []):
            if (event.get("domain") != DOMAIN
                    or event.get("event_type") != "command_applied"
                    or str(event.get("entity_id", "")) != app_id):
                continue
            payload = event.get("payload") or {}
            for change in payload.get("changes") or []:
                collection = str(change.get("collection"))
                record_id = str(change.get("record_id"))
                bucket = records.setdefault(collection, {})
                if change.get("after") is None:
                    bucket.pop(record_id, None)
                else:
                    bucket[record_id] = _json_copy(change["after"], "event record")
            revision = int(payload.get("revision", revision))
            command_id = str(payload.get("command_id", ""))
            if command_id:
                receipts[command_id] = {
                    "payload": payload,
                    "commit": commit,
                    "epoch": transaction.get("epoch") or status.get("epoch"),
                    "state_hash": transaction.get("state_hash"),
                }
    return {
        "app_id": app_id,
        "revision": revision,
        "records": records,
        "receipts": receipts,
        "epoch": status.get("epoch"),
        "commit": int(status.get("commit", 0)),
        "state_hash": status.get("state_hash"),
    }


def _public_context(state):
    return {
        "app_id": state["app_id"],
        "revision": state["revision"],
        "records": {
            collection: [bucket[key] for key in sorted(bucket)]
            for collection, bucket in sorted(state["records"].items())
        },
        "epoch": state["epoch"],
        "commit": state["commit"],
        "state_hash": state["state_hash"],
    }


def _cache_path(root, app_id):
    return Path(root) / ".runtime" / "application_contract_cache" / (app_id + ".json")


def _read_cache(root, app_id):
    path = _cache_path(root, app_id)
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        body = {
            "schema_version": envelope.get("schema_version"),
            "state": envelope.get("state"),
        }
        expected = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        if body["schema_version"] != CACHE_SCHEMA or envelope.get("checksum") != expected:
            return None
        state = body["state"]
        if not isinstance(state, dict) or state.get("app_id") != app_id:
            return None
        return state
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return None


def _write_cache(root, state):
    body = {"schema_version": CACHE_SCHEMA, "state": state}
    envelope = {
        **body,
        "checksum": hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest(),
    }
    _atomic_json(_cache_path(root, state["app_id"]), envelope)


def _write_cache_status(root, state):
    try:
        _write_cache(root, state)
        return {"ok": True, "commit": state["commit"]}
    except Exception as exc:
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}


def _load_service_state(root, app_id, call_fn=_call_atomspace):
    state = _load_state(
        app_id, call_fn=call_fn, initial_state=_read_cache(root, app_id),
    )
    return state, _write_cache_status(root, state)


def read_context(app_id, call_fn=_call_atomspace, through_commit=None):
    """Reconstruct one app from authoritative domain events."""
    return _public_context(_load_state(
        app_id, call_fn=call_fn, through_commit=through_commit,
    ))


def _change(collection, record_id, before, after, operation):
    return {
        "collection": collection,
        "record_id": record_id,
        "before": _json_copy(before, "before record") if before is not None else None,
        "after": _json_copy(after, "after record") if after is not None else None,
        "operation": operation,
    }


def _receipt(app_id, command, receipt, duplicate):
    payload = receipt["payload"]
    changes = _json_copy(payload.get("changes") or [], "receipt changes")
    result = {
        "app_id": app_id,
        "command_id": command["command_id"],
        "type": command["type"],
        "revision": int(payload["revision"]),
        "commit": int(receipt["commit"]),
        "epoch": receipt.get("epoch"),
        "state_hash": receipt.get("state_hash"),
        "duplicate": bool(duplicate),
        "changes": changes,
    }
    if len(changes) == 1:
        result["record"] = changes[0].get("after")
    return result


def apply_command(app_id, consumer_id, raw_command, call_fn=_call_atomspace,
                  commit_batch_fn=commit_batch, initial_state=None):
    """Validate and atomically append one typed application command."""
    app_id = _identifier(app_id, "app_id")
    consumer_id = _identifier(consumer_id, "consumer_id")
    command = _normalise_command(raw_command)
    fingerprint = hashlib.sha256(_canonical({
        "app_id": app_id,
        "consumer_id": consumer_id,
        "command": command,
    }).encode("utf-8")).hexdigest()
    state = _load_state(
        app_id, call_fn=call_fn, initial_state=initial_state,
    )
    previous_receipt = state["receipts"].get(command["command_id"])
    if previous_receipt:
        if previous_receipt["payload"].get("command_fingerprint") != fingerprint:
            raise ValueError("command_id was already used with a different payload")
        return _receipt(app_id, command, previous_receipt, True)
    if command["expected_revision"] != state["revision"]:
        raise StaleRevision(
            "stale application revision: expected %d, current %d"
            % (command["expected_revision"], state["revision"])
        )

    records = state["records"]
    changes = []
    if command["type"] in {"create", "replace"}:
        collection = command["collection"]
        record = command["record"]
        current = records.get(collection, {}).get(record["id"])
        if command["type"] == "create" and current is not None:
            raise ValueError("record already exists")
        if command["type"] == "replace" and current is None:
            raise ValueError("cannot replace a missing record")
        changes.append(_change(
            collection, record["id"], current, record, command["type"],
        ))
    elif command["type"] == "delete":
        collection = command["collection"]
        current = records.get(collection, {}).get(command["record_id"])
        if current is None:
            raise ValueError("cannot delete a missing record")
        changes.append(_change(
            collection, command["record_id"], current, None, "delete",
        ))
    elif command["type"] == "import":
        for collection in sorted(command["collections"]):
            for record in command["collections"][collection]:
                current = records.get(collection, {}).get(record["id"])
                if current is not None and current != record:
                    raise ValueError("import conflicts with an existing record")
                if current is None:
                    changes.append(_change(
                        collection, record["id"], None, record, "import",
                    ))
    else:
        target = state["receipts"].get(command["target_command_id"])
        if target is None:
            raise ValueError("undo target command does not exist")
        target_changes = target["payload"].get("changes") or []
        if not target_changes:
            raise ValueError("undo target has no material changes")
        for original in reversed(target_changes):
            collection = str(original["collection"])
            record_id = str(original["record_id"])
            current = records.get(collection, {}).get(record_id)
            if current != original.get("after"):
                raise ValueError("cannot undo a command after a later record change")
            changes.append(_change(
                collection, record_id, current, original.get("before"), "undo",
            ))

    revision = state["revision"] + 1
    event_id = str(uuid.uuid4())
    payload = {
        "app_id": app_id,
        "consumer_id": consumer_id,
        "command_id": command["command_id"],
        "command_type": command["type"],
        "command_fingerprint": fingerprint,
        "base_revision": state["revision"],
        "revision": revision,
        "provenance": command["provenance"],
        "changes": changes,
    }
    state_atoms = {
        "application_revision:%s" % app_id: " ".join((
            "(application-revision", metta_string(app_id), str(revision),
            metta_string(command["command_id"]), ")",
        )),
        "application_command:%s:%s" % (app_id, command["command_id"]): " ".join((
            "(application-command", metta_string(app_id),
            metta_string(command["command_id"]), metta_string(command["type"]),
            metta_string(fingerprint), str(revision), ")",
        )),
    }
    remove_state_keys = []
    for change in changes:
        collection = change["collection"]
        record_id = change["record_id"]
        before = change.get("before")
        after = change.get("after")
        if after is None:
            remove_state_keys.append(_state_key(app_id, collection, record_id))
            for field in (before or {}):
                remove_state_keys.append(_field_key(
                    app_id, collection, record_id, field,
                ))
            continue
        state_atoms[_state_key(app_id, collection, record_id)] = _record_atom(
            app_id, collection, after, revision, command["provenance"],
            command["command_id"],
        )
        for field, value in after.items():
            state_atoms[_field_key(app_id, collection, record_id, field)] = (
                _field_atom(app_id, collection, record_id, field, value, revision)
            )
        for field in set((before or {})) - set(after):
            remove_state_keys.append(_field_key(
                app_id, collection, record_id, field,
            ))

    committed = commit_batch_fn(
        [{
            "event_id": event_id,
            "domain": DOMAIN,
            "entity_id": app_id,
            "event_type": "command_applied",
            "payload": payload,
        }],
        state_atoms=state_atoms,
        remove_state_keys=remove_state_keys,
        actor=command["provenance"]["actor"],
        source="application_contract.%s" % consumer_id,
        transaction_id="application:%s:%s" % (app_id, command["command_id"]),
    )
    receipt = {
        "payload": payload,
        "commit": committed.get("commit"),
        "epoch": committed.get("epoch"),
        "state_hash": committed.get("state_hash"),
    }
    return _receipt(app_id, command, receipt, committed.get("duplicate", False))


def read_changes(app_id, after_commit, call_fn=_call_atomspace):
    """Return domain events after a commit for polling subscriptions."""
    app_id = _identifier(app_id, "app_id")
    after_commit = int(after_commit or 0)
    status, transactions = _domain_transactions(call_fn, after_commit=after_commit)
    events = []
    for transaction in transactions:
        for event in (transaction.get("metadata") or {}).get("domain_events", []):
            if (event.get("domain") == DOMAIN
                    and event.get("event_type") == "command_applied"
                    and str(event.get("entity_id", "")) == app_id):
                events.append({
                    **_json_copy(event.get("payload") or {}, "application event"),
                    "commit": int(transaction.get("commit", 0)),
                })
    return {
        "app_id": app_id,
        "after_commit": after_commit,
        "events": events,
        "epoch": status.get("epoch"),
        "commit": int(status.get("commit", 0)),
        "state_hash": status.get("state_hash"),
    }


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent),
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def rebuild_json_projection(app_id, projection_dir, call_fn=_call_atomspace,
                            context=None):
    """Rebuild the CRM compatibility JSON solely from canonical events."""
    app_id = _identifier(app_id, "app_id")
    if app_id != "crm":
        raise ValueError("no JSON projection is registered for app_id")
    context = context or read_context(app_id, call_fn=call_fn)
    projection_dir = Path(projection_dir)
    for collection in CRM_COLLECTIONS:
        _atomic_json(
            projection_dir / (collection + ".json"),
            context["records"].get(collection, []),
        )
    return {
        "app_id": app_id,
        "revision": context["revision"],
        "commit": context["commit"],
        "projection_dir": str(projection_dir),
    }


def _projection_status(app_id, projection_dir, context=None):
    """Keep projection failure from obscuring an acknowledged authority write."""
    try:
        return {
            "ok": True,
            **rebuild_json_projection(app_id, projection_dir, context=context),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": "%s: %s" % (type(exc).__name__, exc),
        }


def _service_lock(root):
    lock_path = root / ".runtime" / "application_contract.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _bootstrap_crm(root, consumer_id, state):
    imported = next((
        receipt for receipt in state["receipts"].values()
        if receipt["payload"].get("command_type") == "import"
        and receipt["payload"].get("consumer_id") == "platform.migration"
    ), None)
    if imported is None:
        projection = root / "crm" / "data"
        collections = {}
        for collection in CRM_COLLECTIONS:
            path = projection / (collection + ".json")
            value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            if not isinstance(value, list):
                raise ValueError("CRM compatibility projection must be an array")
            collections[collection] = value
        command = {
            "command_id": "crm-projection-bootstrap-v1",
            "type": "import",
            "expected_revision": state["revision"],
            "provenance": {
                "type": "imported",
                "source": "crm/data/*.json",
                "actor": "platform.migration",
            },
            "collections": collections,
        }
        result = apply_command(
            "crm", "platform.migration", command, initial_state=state,
        )
    else:
        result = {
            "app_id": "crm",
            "command_id": imported["payload"]["command_id"],
            "revision": imported["payload"]["revision"],
            "commit": imported["commit"],
            "duplicate": True,
        }
    return {"command": result, "consumer_id": consumer_id}


def service(request):
    if not isinstance(request, dict):
        raise ValueError("application service request must be an object")
    root = Path(os.environ.get("ITER_DIR") or Path(__file__).resolve().parents[1]).resolve()
    action = str(request.get("action", "")).strip().lower()
    app_id = _identifier(request.get("app_id"), "app_id")
    consumer_id = _identifier(request.get("consumer_id"), "consumer_id")
    if action == "changes":
        return read_changes(app_id, request.get("after_commit", 0))
    lock = _service_lock(root)
    try:
        state, cache_status = _load_service_state(root, app_id)
        if action == "context":
            return {**_public_context(state), "cache": cache_status}
        if action == "bootstrap":
            if app_id != "crm":
                raise ValueError("bootstrap is not registered for app_id")
            result = _bootstrap_crm(root, consumer_id, state)
            current = _load_state(app_id, initial_state=state)
            cache_status = _write_cache_status(root, current)
            projection = _projection_status(
                app_id, root / "crm" / "data", context=_public_context(current),
            )
            return {**result, "cache": cache_status, "projection": projection}
        if action == "rebuild_projection":
            return rebuild_json_projection(
                app_id, root / "crm" / "data", context=_public_context(state),
            )
        if action == "command":
            result = apply_command(
                app_id, consumer_id, request.get("command"), initial_state=state,
            )
            current = _load_state(app_id, initial_state=state)
            cache_status = _write_cache_status(root, current)
            projection = None
            if app_id == "crm":
                projection = _projection_status(
                    app_id, root / "crm" / "data", context=_public_context(current),
                )
            return {**result, "cache": cache_status, "projection": projection}
        raise ValueError("unknown application service action")
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


def main():
    request = json.load(sys.stdin)
    result = service(request)
    json.dump({"ok": True, "result": result}, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        json.dump({
            "ok": False,
            "error": "%s: %s" % (type(exc).__name__, exc),
        }, sys.stdout, ensure_ascii=False, sort_keys=True)
        sys.stdout.write("\n")
        raise SystemExit(2)
