"""Shared cognitive-event transactions for legacy store migration.

Domain code commits authoritative event/state atoms first, then updates its
existing file as a compatibility projection or index. A failed authoritative
commit raises and the projection must not advance.
"""

import hashlib
import json
import os
import re
import socket
import time
import uuid


SOCKET_PATH = os.environ.get("ITER_METTA_SOCKET", "/tmp/iter-metta-bridge.sock")

# C0 controls that JSON escapes in a form Hyperon's tokenizer rejects
# (\u00XX, \b, \f).  \t \n \r are accepted by both and stay as JSON writes them.
_HYPERON_UNSAFE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SIMPLE_ESCAPES = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def metta_string(value):
    """Quote `value` as a MeTTa string literal Hyperon accepts.

    Strings without problem control characters are encoded exactly as before
    (json.dumps, ensure_ascii=False), so existing atoms keep their bytes and
    hashes.  Other C0 controls use Hyperon's own \\u{hex} form.  NUL becomes
    U+FFFD: Hyperon aborts the whole process when it serialises a NUL.
    """
    text = str(value)
    if not _HYPERON_UNSAFE.search(text):
        return json.dumps(text, ensure_ascii=False)
    out = ['"']
    for char in text:
        if char in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[char])
        elif char == "\x00":
            out.append("\ufffd")
        elif ord(char) < 0x20:
            out.append("\\u{%x}" % ord(char))
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


_UNESCAPE = {'"': '"', "\\": "\\", "/": "/", "n": "\n", "r": "\r", "t": "\t",
             "b": "\b", "f": "\f", "0": "\x00"}


def read_metta_string(text, pos=0):
    """Decode the string literal starting at text[pos]; return (value, end).

    Accepts what metta_string writes (JSON escapes plus Hyperon's \\u{hex} and
    \\xHH), so atoms written before and after the escaping change parse alike.
    """
    if pos >= len(text) or text[pos] != '"':
        raise ValueError("expected a string literal at %d" % pos)
    out = []
    index = pos + 1
    while index < len(text):
        char = text[index]
        if char == '"':
            return "".join(out), index + 1
        if char != "\\":
            out.append(char)
            index += 1
            continue
        marker = text[index + 1:index + 2]
        if marker in _UNESCAPE:
            out.append(_UNESCAPE[marker])
            index += 2
        elif marker == "u" and text[index + 2:index + 3] == "{":
            close = text.index("}", index + 3)
            out.append(chr(int(text[index + 3:close], 16)))
            index = close + 1
        elif marker == "u":
            code = int(text[index + 2:index + 6], 16)
            index += 6
            if 0xD800 <= code < 0xDC00 and text[index:index + 2] == "\\u":
                low = int(text[index + 2:index + 6], 16)
                if 0xDC00 <= low < 0xE000:
                    code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                    index += 6
            out.append(chr(code))
        elif marker == "x":
            out.append(chr(int(text[index + 2:index + 4], 16)))
            index += 4
        else:
            raise ValueError("invalid escape \\%s at %d" % (marker, index))
    raise ValueError("unterminated string literal")


def parse_metta_string(literal):
    value, end = read_metta_string(literal.strip())
    if end != len(literal.strip()):
        raise ValueError("trailing content after string literal")
    return value


SEMANTIC_PREFIX = "state:semantic_memory:"


def parse_semantic_atom(key, atom):
    """Parse `(semantic-memory "id" "document" "metadata-json")` without MeTTa."""
    head = "(semantic-memory "
    if not isinstance(atom, str) or not atom.startswith(head):
        raise ValueError("not a semantic memory atom")
    parts = []
    pos = len(head)
    for _ in range(3):
        while pos < len(atom) and atom[pos].isspace():
            pos += 1
        value, pos = read_metta_string(atom, pos)
        parts.append(value)
    if atom[pos:].strip() != ")":
        raise ValueError("semantic memory atom has trailing content")
    if key is not None and parts[0] != key[len(SEMANTIC_PREFIX):]:
        raise ValueError("semantic memory identity differs from authority key")
    metadata = json.loads(parts[2])
    if not isinstance(metadata, dict):
        raise ValueError("semantic memory metadata is not an object")
    return parts[0], parts[1], metadata


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
