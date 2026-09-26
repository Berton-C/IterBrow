import json
import hashlib
import re
import os
import sys
import time
import shutil
from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parents[1]
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from iterbrow_runtime.cognitive_events import commit_batch, commit_event, metta_string


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _mkdirs(path):
    current = ""
    for part in str(path).split("/"):
        if not part:
            current = "/" if not current else current
            continue
        current = (current.rstrip("/") + "/" + part) if current else part
        try:
            os.mkdir(current)
        except OSError:
            pass

DESCRIPTION = "Tracks reliability of tools"

ROOT = "."
RUNTIME_DIR = ROOT + "/transformations/.runtime"
RELIABILITY_FILE = RUNTIME_DIR + "/tool_reliability.json"
STATE_FILE = RUNTIME_DIR + "/tool_reliability_state.txt"
ISSUE_LOG = RUNTIME_DIR + "/tracker_issues.log"
PENDING_BATCH_FILE = RUNTIME_DIR + "/tool_reliability_pending_batch.json"
NACE_PENDING_FILE = ROOT + "/nace_pending.metta"
MAX_OUTCOMES_PER_BATCH = 12
# Leave time to retain the prepared batch before the host's 15s deadline.
# A timed-out commit may still finish; retry its SAME transaction, never rescore.
COMMIT_TIMEOUT = 8
NACE_MARKER_PREFIX = ";; tool-reliability-event "

def _log_issue(detail):
    # Best-effort diagnostic trail only -- never allowed to raise or block
    # reliability recording itself.
    try:
        with open(ISSUE_LOG, "a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "detail": detail}) + "\n")
    except Exception:
        pass


def _atomic_write_text(path, content):
    directory = os.path.dirname(path) or "."
    _mkdirs(directory)
    temporary = "%s.tmp.%s" % (path, os.getpid())
    with open(temporary, "w") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _atomic_write_json(path, value):
    _atomic_write_text(path, json.dumps(value, sort_keys=True))


def _read_scores():
    if not _exists(RELIABILITY_FILE):
        return {}
    try:
        with open(RELIABILITY_FILE, "r") as handle:
            value = json.loads(handle.read())
        return value if isinstance(value, dict) else {}
    except Exception as e:
        _log_issue("tool_reliability.json unreadable/corrupt, starting fresh scores this call: %s: %s" % (type(e).__name__, e))
        try:
            shutil.copy(RELIABILITY_FILE, RELIABILITY_FILE + ".corrupt.%d.bak" % int(time.time()))
        except Exception:
            pass
        return {}


def _apply_outcome(scores, tool_name, success):
    if tool_name not in scores:
        scores[tool_name] = {"f": 0.5, "c": 0.0, "calls": 0, "successes": 0, "failures": 0}
    s = scores[tool_name]
    calls = s.get("calls", 0)
    if calls < 1:
        s["f"] = 1.0 if success else 0.0
        s["c"] = 0.5
    else:
        obs_f = 1.0 if success else 0.0
        s["f"], s["c"] = nal_revise(s["f"], s["c"], obs_f, 0.5)
    s["calls"] = calls + 1
    if success:
        s["successes"] = s.get("successes", 0) + 1
    else:
        s["failures"] = s.get("failures", 0) + 1
    scores[tool_name] = s
    return dict(s)


def _write_processed_ids(processed_ids):
    _atomic_write_text(STATE_FILE, "\n".join(sorted(processed_ids)))


def _append_nace_entries(entries):
    """Project each committed outcome to NACE exactly once.

    The adjacent marker makes an interrupted pending-batch replay idempotent.
    nace_courier removes the marker together with the pending revision.
    """
    try:
        with open(NACE_PENDING_FILE, "r") as handle:
            content = handle.read()
    except Exception:
        content = ""
    existing = set(line.strip() for line in content.splitlines())
    changed = False
    if content and not content.endswith("\n"):
        content += "\n"
    for entry in entries:
        marker = NACE_MARKER_PREFIX + entry["tool_call_id"]
        if marker in existing:
            continue
        content += entry["line"] + "\n" + marker + "\n"
        existing.add(marker)
        changed = True
    if changed:
        _atomic_write_text(NACE_PENDING_FILE, content)


def _finish_pending_batch(record):
    """Replay/finalize one prepared batch without double-revising projections."""
    result = commit_batch(
        record["domain_events"],
        state_atoms=record["state_atoms"],
        actor="iter",
        source="transformations.tool_reliability_tracker",
        transaction_id=record["transaction_id"],
        timeout=COMMIT_TIMEOUT,
    )
    if result.get("deferred"):
        raise RuntimeError("Reliability commit deferred: " + result.get("reason", "authority unavailable"))
    _atomic_write_json(RELIABILITY_FILE, record["scores_after"])
    _write_processed_ids(record["processed_ids"])
    _append_nace_entries(record["nace_entries"])
    try:
        os.unlink(PENDING_BATCH_FILE)
    except FileNotFoundError:
        pass


def _recover_pending_batch():
    if not _exists(PENDING_BATCH_FILE):
        return False
    try:
        with open(PENDING_BATCH_FILE, "r") as handle:
            record = json.loads(handle.read())
        _finish_pending_batch(record)
        return True
    except Exception as e:
        _log_issue("pending reliability batch recovery failed: %s: %s" % (type(e).__name__, e))
        return False

def nal_revise(f1, c1, f2, c2):
    w1 = c1 / (1 - c1) if c1 < 1.0 else 1e10
    w2 = c2 / (1 - c2) if c2 < 1.0 else 1e10
    f_new = (w1 * f1 + w2 * f2) / (w1 + w2)
    c_new = (w1 + w2) / (w1 + w2 + 1)
    return round(f_new, 4), round(c_new, 4)

def update_reliability(tool_name, success, event_id=""):
    try:
        _mkdirs(RUNTIME_DIR)
    except OSError:
        pass
    scores = _read_scores()
    s = _apply_outcome(scores, tool_name, success)
    try:
        result = commit_event(
            "tool_reliability", tool_name, "outcome_recorded",
            {"success": bool(success), "score": s, "tool_call_id": event_id},
            state_atom="(tool-reliability %s (stv %s %s) %s %s %s)" % (
                metta_string(tool_name), s["f"], s["c"], s["calls"],
                s.get("successes", 0), s.get("failures", 0),
            ),
            event_id=("tool-outcome:%s" % event_id) if event_id else None,
            transaction_id=("cognitive:tool-outcome:%s" % event_id) if event_id else None,
            source="transformations.tool_reliability_tracker",
            timeout=COMMIT_TIMEOUT,
        )
        if result.get("deferred"):
            raise RuntimeError("Reliability commit deferred: " + result.get("reason", "authority unavailable"))
    except Exception as e:
        _log_issue("authoritative reliability commit failed; projection not advanced: %s: %s" % (type(e).__name__, e))
        return False
    try:
        _atomic_write_json(RELIABILITY_FILE, scores)
    except Exception as e:
        _log_issue("reliability projection failed after authoritative commit: %s: %s" % (type(e).__name__, e))
        return False
    return True

# Specific error patterns that indicate actual tool failures.
# Avoids false positives from memory text containing words like "error", "failed", etc.
ERROR_PATTERNS = [
    r"traceback\s*\(most recent call last\)",
    r"tool execution failed",
    r"\bsyntaxerror\b",
    r"\bnameerror\b",
    r"\btypeerror\b",
    r"\bvalueerror\b",
    r"\bimporterror\b",
    r"\battributeerror\b",
    r"\bkeyerror\b",
    r"\bindexerror\b",
    r"\bruntimeerror\b",
    r"\boserror\b",
    r"\bpermissionerror\b",
    r"\bfilenotfounderror\b",
    r"\benoent\b",
    r"no such file or directory",
    r"connection refused",
    r"connection reset",
    r"network unreachable",
    r"jsondecodeerror",
]

# Tools that return historical/transcript/memory text containing error keywords
# by nature. These should always be counted as success since the presence of
# error words in their output is expected (they return records of past errors,
# not tool failures).
EXEMPT_TOOLS = {"episodes", "search_transcript", "chroma_query"}

def has_error(content):
    lower = content.lower()
    for pattern in ERROR_PATTERNS:
        if re.search(pattern, lower):
            return True
    return False

def transform(messages, tools):
    # Finish an interrupted batch first. Its deterministic transaction and
    # exact scores_after snapshot make every recovery step replay-safe.
    if _exists(PENDING_BATCH_FILE):
        _recover_pending_batch()
        return messages, tools

    try:
        with open(STATE_FILE, "r") as file:
            previous_ids = set(line.strip() for line in file if line.strip())
    except Exception:
        previous_ids = set()

    call_names = {}
    message_ids = set()
    results = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls", []):
                if not isinstance(tc, dict) or not tc.get("id"):
                    continue
                tool_name = (tc.get("function") or {}).get("name", "")
                if tool_name:
                    call_names[tc["id"]] = tool_name
        elif msg.get("role") == "tool":
            tool_call_id = msg.get("tool_call_id", "")
            content = msg.get("content", "")
            if tool_call_id and content:
                message_ids.add(tool_call_id)
                results.append((tool_call_id, msg.get("_iter_execution")))

    processed_ids = previous_ids.intersection(message_ids)
    pending = []
    for tool_call_id, execution in results:
        if tool_call_id in previous_ids:
            continue
        tool_name = call_names.get(tool_call_id, "")
        if not tool_name:
            # Preserve the historical behavior for a truncated assistant/tool
            # pair: there is no safe tool identity to revise, so do not spin on
            # the orphaned result forever.
            processed_ids.add(tool_call_id)
            continue
        if len(pending) >= MAX_OUTCOMES_PER_BATCH:
            continue
        # Never infer execution failure from quoted history/error words, or
        # exempt a real memory-tool exception. Old unstructured results remain
        # unknown, without resetting already committed historical beliefs.
        success = execution.get("success") if isinstance(execution, dict) else None
        if type(success) is not bool:
            processed_ids.add(tool_call_id)
            continue
        pending.append((tool_call_id, tool_name, success))

    if not pending:
        try:
            _write_processed_ids(processed_ids)
        except Exception as e:
            _log_issue("reliability state projection failed: %s: %s" % (type(e).__name__, e))
        return messages, tools

    scores = _read_scores()
    domain_events = []
    state_atoms = {}
    nace_entries = []
    batch_ids = []
    for tool_call_id, tool_name, success in pending:
        score = _apply_outcome(scores, tool_name, success)
        event_id = "tool-outcome:%s" % tool_call_id
        domain_events.append({
            "event_id": event_id,
            "domain": "tool_reliability",
            "entity_id": tool_name,
            "event_type": "outcome_recorded",
            "payload": {"success": bool(success), "score": score, "tool_call_id": tool_call_id,
                        "evidence_scope": "execution", "task_fulfillment": "unverified"},
        })
        state_atoms["tool_reliability:%s" % tool_name] = (
            "(tool-reliability %s (stv %s %s) %s %s %s)" % (
                metta_string(tool_name), score["f"], score["c"], score["calls"],
                score.get("successes", 0), score.get("failures", 0),
            )
        )
        outcome = "confirmed" if success else "disconfirmed"
        nace_entries.append({
            "tool_call_id": tool_call_id,
            "line": "(pending-revision tool %s %s)" % (tool_name, outcome),
        })
        batch_ids.append(tool_call_id)
        processed_ids.add(tool_call_id)

    batch_digest = hashlib.sha256(
        json.dumps(batch_ids, sort_keys=True).encode("utf-8")
    ).hexdigest()
    record = {
        "schema_version": 1,
        "transaction_id": "cognitive:tool-outcome-batch:%s" % batch_digest,
        "domain_events": domain_events,
        "state_atoms": state_atoms,
        "scores_after": scores,
        "processed_ids": sorted(processed_ids),
        "nace_entries": nace_entries,
    }
    try:
        _atomic_write_json(PENDING_BATCH_FILE, record)
        _finish_pending_batch(record)
    except Exception as e:
        _log_issue("authoritative reliability batch failed; recovery retained: %s: %s" % (type(e).__name__, e))
    return messages, tools
