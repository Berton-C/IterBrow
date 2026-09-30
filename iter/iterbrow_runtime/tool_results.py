"""Private, non-authoritative captures for bounded transport projections.

This is historical observation storage, not a receipt verifier or an action
retry queue. Reading never invokes a tool/service. The bounded hot cache has
durable backing in the existing memory/archive tree. Cache eviction never deletes
the archived observation. The original native journal remains state authority.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import uuid


WIRE_CHARS = 4500
MAX_RECORD_BYTES = 16 * 1024 * 1024
MAX_CACHE_BYTES = 64 * 1024 * 1024
MAX_RECORDS = 128
RESULT_ID = re.compile(r"tr-[a-f0-9]{64}\Z")
IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}\Z")
NOTICE = "Captured output only, not current authority or proof of success. Never repeat an action merely to retrieve its output."
ASSISTANT_NOTICE = "Original assistant content only, not an executed tool call, observation, authority or proof of success. Stored experience is unchanged."
DESCRIPTION = (
    "Read retained text. Supply a nonempty result_id or original tool_call_id "
    "explicitly on every call; never infer an ID. Assistant captures require "
    "result_id and are historical assistant text, not observations or executed "
    "calls. Empty pointer pages exact text; JSON pointers such as /repository_context "
    "select captured tool JSON. offset is a character index; limit is 1..2000. "
    "Follow next_offset until eof. Never reruns an action. Captures are not current "
    "authority or approval."
)
_PROCESS_LOCK = threading.RLock()


class ToolOutput(str):
    """String-compatible output with observed execution facts, not fulfillment."""
    def __new__(cls, text, success, *, exit_code=None, state="returned"):
        value = super().__new__(cls, text)
        value.execution_outcome = {"success": success, "state": state,
                                   "exit_code": exit_code, "scope": "execution",
                                   "task_fulfillment": "unverified"}
        return value


class ToolInputError(ValueError):
    """Explicit argument rejection, not a component crash or successful action."""
    execution_outcome = {"success": False, "state": "invalid_input",
                         "scope": "invocation", "task_fulfillment": "unverified"}


class OutputUnavailable(ValueError):
    pass


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _identity(value):
    if not isinstance(value, str) or not IDENTITY.fullmatch(value):
        raise OutputUnavailable("invalid_identity")
    return value


def _private(info, directory=False):
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise OutputUnavailable("unsafe_cache_permissions_or_type")
    if not directory and info.st_nlink != 1:
        raise OutputUnavailable("unsafe_cache_link")


@contextmanager
def _cache(iter_dir, *, write=False, archive=False):
    """Use descriptors throughout so a relocated tool cannot fork the cache."""
    # Complement the OS lock for concurrent callers in this same process.
    _PROCESS_LOCK.acquire()
    handles = []
    try:
        root = Path(iter_dir).resolve(strict=True)
        current = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        handles.append(current)
        parts = ("memory", "archive", "tool_results") if archive else (".runtime", "tool_results")
        for name in parts:
            if write:
                try:
                    os.mkdir(name, mode=0o700, dir_fd=current)
                except FileExistsError:
                    pass
            current = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            handles.append(current)
        _private(os.fstat(current), directory=True)
        flags = os.O_RDWR | os.O_CREAT if write else os.O_RDONLY
        lock = os.open(".writer.lock", flags | os.O_NOFOLLOW, 0o600, dir_fd=current)
        handles.append(lock)
        _private(os.fstat(lock))
        fcntl.flock(lock, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
        yield current
    finally:
        try:
            for handle in reversed(handles):
                os.close(handle)
        finally:
            _PROCESS_LOCK.release()


def _inventory(directory):
    records = []
    for name in os.listdir(directory):
        if name.endswith(".json") and RESULT_ID.fullmatch(name[:-5]):
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            _private(info)
            records.append((info.st_mtime_ns, name, info.st_size))
    return sorted(records)


def _load(directory, result_id):
    if not isinstance(result_id, str) or not RESULT_ID.fullmatch(result_id):
        raise OutputUnavailable("invalid_result_id")
    handle = os.open(result_id + ".json", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    with os.fdopen(handle, "rb") as stream:
        info = os.fstat(stream.fileno())
        _private(info)
        if info.st_size > MAX_RECORD_BYTES:
            raise OutputUnavailable("oversized_cache_record")
        raw = stream.read(MAX_RECORD_BYTES + 1)
        if len(raw) != info.st_size:
            raise OutputUnavailable("cache_record_changed")
    if "tr-" + hashlib.sha256(raw).hexdigest() != result_id:
        raise OutputUnavailable("cache_hash_mismatch")
    record = json.loads(raw)
    if (record.get("schema_version") not in (1, 2, 3) or not isinstance(record.get("text"), str)
            or _hash(record["text"]) != record.get("text_sha256")):
        raise OutputUnavailable("invalid_cache_record")
    if record["schema_version"] == 2:
        if (record.get("source_kind") != "assistant_message"
                or not isinstance(record.get("message_id"), str)
                or not IDENTITY.fullmatch(record["message_id"])):
            raise OutputUnavailable("invalid_assistant_capture")
    if record["schema_version"] == 3:
        if (record.get("source_kind") != "completed_exchange"
                or not isinstance(record.get("exchange_id"), str)
                or not IDENTITY.fullmatch(record["exchange_id"])):
            raise OutputUnavailable("invalid_exchange_capture")
    return record


def _publish(directory, result_id, data):
    try:
        _load(directory, result_id)
        return
    except FileNotFoundError:
        pass
    name = ".tmp-" + uuid.uuid4().hex
    handle = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            _load(directory, result_id)
        except FileNotFoundError:
            # The filename hashes ALL bytes, including original call metadata.
            # An existing valid identity has identical bytes and is left alone.
            # Rename avoids a crash window with two hardlinks to one record.
            os.replace(name, result_id + ".json", src_dir_fd=directory, dst_dir_fd=directory)
    finally:
        try:
            os.unlink(name, dir_fd=directory)
        except FileNotFoundError:
            pass
    os.fsync(directory)


def _retain(directory, result_id, data, archive):
    if len(data) > min(MAX_RECORD_BYTES, MAX_CACHE_BYTES) or MAX_RECORDS < 1:
        raise OutputUnavailable("result_exceeds_retention_capacity")
    _publish(archive, result_id, data)
    try:
        _load(directory, result_id)
        return  # Re-projecting identical assistant content must not churn records.
    except FileNotFoundError:
        pass
    # A writer crash can leave an unpublished temporary file; it is never read
    # as a result. Clean only our validated private temporary files under lock.
    for name in os.listdir(directory):
        if re.fullmatch(r"\.tmp-[a-f0-9]{32}", name):
            _private(os.stat(name, dir_fd=directory, follow_symlinks=False))
            os.unlink(name, dir_fd=directory)
    inventory = _inventory(directory)
    total = sum(item[2] for item in inventory)
    while inventory and (len(inventory) >= MAX_RECORDS or total + len(data) > MAX_CACHE_BYTES):
        _, name, size = inventory.pop(0)
        # Includes captures made before durable backing was installed.
        _publish(archive, name[:-5], _json(_load(directory, name[:-5])).encode("utf-8"))
        os.unlink(name, dir_fd=directory)
        total -= size
    _publish(directory, result_id, data)


def _save_capture(iter_dir, result_id, data):
    with _cache(iter_dir, write=True) as directory:
        with _cache(iter_dir, write=True, archive=True) as archive:
            _retain(directory, result_id, data, archive)


def archive_cached_outputs(iter_dir):
    """One-time startup handoff for pre-existing captures; never run an action."""
    try:
        with _cache(iter_dir) as directory:
            with _cache(iter_dir, write=True, archive=True) as archive:
                for _, name, _ in _inventory(directory):
                    _publish(archive, name[:-5], _json(_load(directory, name[:-5])).encode("utf-8"))
    except FileNotFoundError:
        pass  # A fresh installation has no observations to migrate.


def _read_capture(iter_dir, result_id):
    try:
        with _cache(iter_dir) as directory:
            return _load(directory, result_id)
    except FileNotFoundError:
        with _cache(iter_dir, archive=True) as archive:
            return _load(archive, result_id)


def _find_capture(iter_dir, tool_call_id):
    # Explicit result_id reads use direct lookup. This legacy selector searches
    # both stores and detects ambiguity rather than choosing an arbitrary result.
    matches = {}
    for archived in (False, True):
        try:
            with _cache(iter_dir, archive=archived) as directory:
                for _, name, _ in _inventory(directory):
                    if name[:-5] in matches:
                        continue
                    candidate = _load(directory, name[:-5])
                    if candidate.get("tool_call_id") == tool_call_id:
                        matches[name[:-5]] = candidate
        except FileNotFoundError:
            continue
    if len(matches) != 1:
        raise OutputUnavailable("ambiguous_tool_call_id" if matches else "result_missing_or_evicted")
    return next(iter(matches.items()))


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _not_json_constant(value):
    raise ValueError("non-finite JSON constant")


def _raw_json(raw_result):
    if raw_result is None:
        return False, None
    try:
        text = raw_result if isinstance(raw_result, str) else _json(raw_result)
        return True, json.loads(text, object_pairs_hook=_strict_object, parse_constant=_not_json_constant)
    except (ValueError, TypeError, RecursionError):
        return False, None


def _fitted(make, length, max_chars=WIRE_CHARS):
    """Fit serialized JSON, including escaping and metadata, not raw text size."""
    low, high = 0, length
    best = _json(make(0))
    if len(best) > max_chars:
        raise OutputUnavailable("response_metadata_exceeds_wire_budget")
    while low <= high:
        middle = (low + high) // 2
        candidate = _json(make(middle))
        if len(candidate) <= max_chars:
            best, low = candidate, middle + 1
        else:
            high = middle - 1
    return best


def _failure(code, *, text="", max_chars=WIRE_CHARS):
    base = {"kind": "tool_output_unavailable", "retained": False,
            "non_authoritative": True, "error": code, "notice": NOTICE}
    return _fitted(lambda n: {**base, "original_prefix": text[:n]}, min(len(text), 1000), max_chars)


def _error_code(exc):
    if isinstance(exc, OutputUnavailable):
        return str(exc)
    if isinstance(exc, FileNotFoundError):
        return "result_missing_or_evicted"
    if isinstance(exc, OSError):
        return "cache_io_error:" + str(exc.errno)
    return "invalid_or_unavailable_capture:" + type(exc).__name__


def _metadata(record, result_id):
    if record.get("source_kind") == "completed_exchange":
        return {key: record[key] for key in (
            "source_kind", "exchange_id", "generation_id", "text_sha256", "text_chars"
        )} | {"result_id": result_id, "artifact_sha256": result_id[3:],
              "json_pointer_available": True}
    if record.get("source_kind") == "assistant_message":
        return {key: record[key] for key in (
            "source_kind", "message_id", "generation_id", "text_sha256", "text_chars"
        )} | {"result_id": result_id, "artifact_sha256": result_id[3:],
              "json_pointer_available": False}
    return {key: record[key] for key in (
        "tool_call_id", "tool_name", "generation_id", "captured_at", "text_sha256", "text_chars"
    )} | {"result_id": result_id, "artifact_sha256": result_id[3:],
          "advisory": record["advisory"][:256], "advisory_chars": len(record["advisory"]),
          "advisory_truncated": len(record["advisory"]) > 256,
          "json_pointer_available": record["json_available"]}


def output_excerpt(text, limit):
    """Show setup and final diagnostics; middle text stays explicitly omitted."""
    if len(text) <= limit:
        return {"preview": text, "tail": "", "tail_offset": len(text), "omitted_chars": 0}
    head = limit // 3
    tail = limit - head
    return {"preview": text[:head], "tail": text[len(text) - tail:] if tail else "",
            "tail_offset": len(text) - tail, "omitted_chars": len(text) - limit}


def execution_facts(execution):
    """Only observed invocation facts, never an inferred task-completion claim."""
    if not isinstance(execution, dict):
        return {}
    return {key: value for key, value in execution.items()
            if key in ("success", "state", "scope", "exit_code", "task_fulfillment")
            and (value is None or type(value) in (bool, int)
                 or isinstance(value, str) and len(value) <= 80)}


def capture_tool_output(iter_dir, text, *, tool_call_id, tool_name, generation_id,
                        raw_result=None, advisory="", max_chars=4500, execution=None):
    """Never retry or raise a capture failure after the original tool has run."""
    budget = WIRE_CHARS
    try:
        if type(max_chars) is not int or not 512 <= max_chars <= WIRE_CHARS:
            raise OutputUnavailable("wire_budget_must_be_512_through_4500")
        budget = max_chars
        if not isinstance(text, str):
            raise OutputUnavailable("output_text_must_be_string")
        if len(text) <= budget:
            return text
        json_available, value = _raw_json(raw_result)
        record = {"schema_version": 1, "tool_call_id": _identity(tool_call_id),
            "tool_name": _identity(tool_name), "generation_id": _identity(generation_id),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "text": text, "text_sha256": _hash(text), "text_chars": len(text),
            "advisory": str(advisory), "json_available": json_available, "raw_json": value}
        data = _json(record).encode("utf-8")
        result_id = "tr-" + hashlib.sha256(data).hexdigest()
        base = {"kind": "retained_tool_output", "retained": True, "non_authoritative": True,
                **_metadata(record, result_id), "notice": NOTICE,
                "read": "read_tool_result(tool_call_id=%s, offset=0, limit=2000); %s" % (
                    _json(record["tool_call_id"]),
                    "omit pointer for exact text; an optional pointer selects an existing original JSON field" if json_available else
                    "plain text: omit pointer")}
        if execution_facts(execution):
            base["execution_outcome"] = execution_facts(execution)
        envelope = _fitted(lambda n: {**base, **output_excerpt(text, n)}, min(len(text), 1800), budget)
        _save_capture(iter_dir, result_id, data)
        return envelope
    except Exception as exc:
        # Do not include OS paths or candidate-supplied exception contents.
        return _failure(_error_code(exc), text=text if isinstance(text, str) else "", max_chars=budget)


def restore_tool_observation(iter_dir, message, max_chars):
    """Restore a captured observation or explicitly requested raw-text page.

    The caller decides whether the complete text fits its request. An unavailable
    or oversized record leaves the existing preview and manual reader unchanged.
    """
    content = message.get("content", "")
    if message.get("role") != "tool" or not isinstance(content, str):
        return None
    prefix, body = "", content
    if content.startswith("Step ") and ": " in content:
        prefix, body = content.split(": ", 1)
        prefix += ": "
    try:
        envelope = json.loads(body)
        if isinstance(envelope, dict) and envelope.get("kind") == "tool_output_page":
            # A reader has its own call ID; the envelope identifies the original
            # observation. Let the request budget prefer this newly requested
            # source instead of repeatedly restoring an older unrelated capture.
            # Pointer reads stay scoped to their selected fields and are unchanged.
            if (envelope.get("pointer") != "" or envelope.get("content_format") != "text"
                    or type(envelope.get("total_chars")) is not int
                    or not 0 <= envelope["total_chars"] <= max_chars - len(prefix)):
                return None
            record = _read_capture(iter_dir, envelope.get("result_id"))
            text = record["text"]
            offset, page = envelope.get("offset"), envelope.get("content")
            if (record.get("schema_version") != 1
                    or record.get("tool_call_id") != envelope.get("tool_call_id")
                    or record.get("text_sha256") != envelope.get("text_sha256")
                    or record.get("text_sha256") != envelope.get("selected_sha256")
                    or len(text) != envelope["total_chars"]
                    or type(offset) is not int or not 0 <= offset <= len(text)
                    or not isinstance(page, str) or text[offset:offset + len(page)] != page):
                return None
            expanded = {**envelope, "content": text, "offset": 0, "eof": True,
                        "next_offset": None,
                        "context_expansion": "Complete historical output for this requested page; not a new tool execution. Stored experience is unchanged."}
            restored = prefix + _json(expanded)
            return restored if len(restored) <= max_chars else None
        if (not isinstance(envelope, dict) or envelope.get("kind") != "retained_tool_output"
                or envelope.get("retained") is not True
                or envelope.get("tool_call_id") != message.get("tool_call_id")
                or type(envelope.get("text_chars")) is not int
                or not 0 <= envelope["text_chars"] <= max_chars - len(prefix)):
            return None
        record = _read_capture(iter_dir, envelope.get("result_id"))
        if (record.get("schema_version") != 1
                or record.get("tool_call_id") != message["tool_call_id"]
                or record.get("text_sha256") != envelope.get("text_sha256")
                or len(record["text"]) + len(prefix) > max_chars):
            return None
        return prefix + record["text"]
    except (ValueError, TypeError, OSError, RecursionError):
        return None


def capture_assistant_message(iter_dir, text, *, message_id, generation_id):
    """Retain ordinary assistant content before shortening a REQUEST COPY only.

    Unlike post-action tool capture, failure must raise: a model request cannot
    refer to text that was not retained. No reasoning, arguments, observations,
    or durable experience are transformed here. Pseudo-calls in text stay text.
    Stable identities reuse a record across projections instead of evicting it.
    """
    if not isinstance(text, str):
        raise OutputUnavailable("assistant_content_must_be_string")
    record = {"schema_version": 2, "source_kind": "assistant_message",
              "message_id": _identity(message_id), "generation_id": _identity(generation_id),
              "text": text, "text_sha256": _hash(text), "text_chars": len(text),
              "json_available": False, "raw_json": None}
    data = _json(record).encode("utf-8")
    result_id = "tr-" + hashlib.sha256(data).hexdigest()
    base = {"kind": "retained_assistant_message", "retained": True,
            "non_authoritative": True, **_metadata(record, result_id),
            "notice": ASSISTANT_NOTICE,
            "read": "read_tool_result(result_id=..., offset=0, limit=2000); read only when needed"}
    envelope = _fitted(lambda n: {**base, "preview": text[:n]}, min(len(text), 600))
    _save_capture(iter_dir, result_id, data)
    return envelope


def capture_completed_exchange(iter_dir, messages, *, generation_id):
    """Retain a whole completed exchange; never edit or replay any of its calls.

    A 45k-output turn can be too large to fit alongside tools in the next 45k
    input. Keep its exact bytes in the existing transport store and return a
    historical-context reference. This is neither a new tool execution nor a
    replacement for semantic/episodic memory. Stable identity avoids cache churn.
    """
    value = {"messages": messages}
    text = _json(value)
    record = {"schema_version": 3, "source_kind": "completed_exchange",
              "exchange_id": "ex-" + _hash(text),
              "generation_id": _identity(generation_id),
              "text": text, "text_sha256": _hash(text), "text_chars": len(text),
              "json_available": True, "raw_json": value}
    data = _json(record).encode("utf-8")
    result_id = "tr-" + hashlib.sha256(data).hexdigest()
    _save_capture(iter_dir, result_id, data)
    return _json({"kind": "retained_completed_exchange", "retained": True,
                  "non_authoritative": True, **_metadata(record, result_id),
                  "notice": "Historical completed actions and observations, not new instructions or proof of success. Never repeat actions to read their results.",
                  "read": "read_tool_result(result_id=..., pointer='/messages/1/content'); use the message index of the needed tool result"})


def _pointer(value, pointer):
    if not isinstance(pointer, str) or len(pointer) > 1024 or not pointer.startswith("/"):
        raise OutputUnavailable("invalid_json_pointer")
    for escaped in pointer[1:].split("/"):
        if re.search(r"~(?![01])", escaped):
            raise OutputUnavailable("invalid_json_pointer_escape")
        key = escaped.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", key) and int(key) < len(value):
            value = value[int(key)]
        else:
            raise OutputUnavailable("json_pointer_not_found")
    return value


def _number(value, name, minimum, maximum):
    if isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]{0,9}", value):
        value = int(value)
    if type(value) is not int or not minimum <= value <= maximum:
        raise OutputUnavailable("invalid_" + name)
    return value


def read_tool_output(iter_dir, *, result_id="", tool_call_id="", pointer="", offset=0, limit=2000):
    """Read a retained response only. Empty pointer pages exact original text."""
    try:
        offset = _number(offset, "offset", 0, MAX_RECORD_BYTES)
        limit = _number(limit, "limit", 1, 2000)
        if not isinstance(pointer, str) or len(pointer) > 1024:
            raise OutputUnavailable("invalid_json_pointer")
        if result_id and (not isinstance(result_id, str) or not RESULT_ID.fullmatch(result_id)):
            raise OutputUnavailable("invalid_result_id")
        if tool_call_id:
            _identity(tool_call_id)
        if not result_id and not tool_call_id:
            raise OutputUnavailable("result_id_or_tool_call_id_required")
        if result_id:
            record = _read_capture(iter_dir, result_id)
            if tool_call_id and record.get("tool_call_id") != tool_call_id:
                raise OutputUnavailable("tool_call_identity_mismatch")
        else:
            result_id, record = _find_capture(iter_dir, tool_call_id)
        if pointer:
            if not record["json_available"]:
                raise OutputUnavailable("original_raw_result_was_not_json")
            selected = _json(_pointer(record["raw_json"], pointer))
        else:
            selected = record["text"]
        if offset > len(selected):
            raise OutputUnavailable("offset_beyond_selected_output")
        assistant = record.get("source_kind") == "assistant_message"
        base = {"kind": "assistant_message_page" if assistant else "tool_output_page", "non_authoritative": True,
                **_metadata(record, result_id), "pointer": pointer,
                "content_format": "json" if pointer else "text", "total_chars": len(selected),
                "selected_sha256": _hash(selected), "offset": offset,
                "notice": ASSISTANT_NOTICE if assistant else NOTICE}
        def page(count):
            end = offset + count
            return {**base, "content": selected[offset:end], "eof": end == len(selected),
                    "next_offset": end if end < len(selected) else None}
        return _fitted(page, min(limit, len(selected) - offset))
    except Exception as exc:
        code = _error_code(exc)
        failed = json.loads(_failure(code))
        failed["recovery"] = (
            "Correct the reference, pointer or offset; omit pointer for plain text. Reading never reruns the tool."
            if code.startswith(("invalid_", "offset_", "result_id_or_", "original_raw_", "json_pointer_", "tool_call_identity_"))
            else "Historical output is unavailable. Obtain a fresh read-only observation of current state; do not repeat a write to recover its output."
        )
        return _json(failed)


def run(result_id="", tool_call_id="", pointer="", offset=0, limit=2000):
    """Host-owned read surface survives managed-component rollback."""
    root = Path(os.getenv("ITER_DIR") or Path.cwd()).resolve()
    return read_tool_output(root, result_id=result_id, tool_call_id=tool_call_id,
                            pointer=pointer, offset=offset, limit=limit)
