"""Connection Depth Bridge -- feeds real evidence into the previously-
dormant `recover_gracefully` NAL compass pattern, reinterpreted through the
flourishing lens the user approved as Connection Depth: "repair becomes
possible without humiliation" applied to the human-AI relationship. A real
error handled and then honestly reported to the user is repair; the same
error patched over in silence is not -- it just hides the moment where
trust could have been rebuilt.

SIGNAL, NOT A NEW ERROR SCANNER: auto_improve.py already defines the
regexes this app uses to recognize a real error in transcript.txt
(ERROR_PATTERNS -- tracebacks, NameError, ConnectionRefused, etc.).
Imported directly here so the two files can never disagree on what counts
as "an error happened". stall_detect.py already established the exact
transcript-tail-parsing convention this reuses (walk `[timestamp] [tool
args]` lines, count calls since the last `send`).

  * an error line appears among the tool calls made SINCE the last `send`,
    and the count of calls since that send has crossed SILENT_THRESHOLD
    (mirrors stall_detect.py's own SILENT_THRESHOLD=5 for the same "the
    user cannot see this, silence looks like nothing happened" reasoning)
    with still no send -> the error is being worked on/around in silence.
    Recorded as `violated`.
  * the window's last call IS a `send`, and an error appears in the
    segment right before it (since the previous send) -> the error was
    surfaced to the user in the same cycle it happened, not swept under
    the rug. Recorded as `confirmed`.

INTEGRATION: mirrors idle_cycle_detector.py's convention -- one
`(pending-revision pattern recover_gracefully <outcome>)` line into
nace_pending.metta via tools/_provenance.record_pattern_outcome, letting
nace_courier.py's normal NAL Truth_Revision cycle do the math. Never
touches auto_improve.py or stall_detect.py, never withholds tools.

Dedup: keyed on the transcript window's own length so the same streak is
not re-recorded every single cycle it persists.

Fails open on any error -- never blocks dispatch, never raises.
"""
import os
import re
import sys
import json

_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
try:
    import _provenance as _prov
except Exception:
    _prov = None

try:
    import auto_improve as _ai
    _ERROR_PATTERNS = _ai.ERROR_PATTERNS
except Exception:
    _ERROR_PATTERNS = [
        r"traceback\s*\(most recent call last\)", r"\bsyntaxerror\b", r"\bnameerror\b",
        r"\btypeerror\b", r"\bvalueerror\b", r"\bimporterror\b", r"\battributeerror\b",
        r"\bkeyerror\b", r"\bindexerror\b", r"\bruntimeerror\b", r"\boserror\b",
        r"no such file or directory", r"connection refused", r"jsondecodeerror",
    ]

DESCRIPTION = "Feeds real confirmed/violated evidence into the recover_gracefully compass pattern (Connection Depth) by checking whether real errors (auto_improve.py's own ERROR_PATTERNS) get surfaced to the user via send, or handled in silence"

TRANSCRIPT_PATH = "transcript.txt"
STATE_PATH = os.path.join("memory", ".connection_depth_state.json")
WINDOW_SIZE = 60
SILENT_THRESHOLD = 5  # mirrors stall_detect.py's own SILENT_THRESHOLD


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _read_json(path):
    if not _exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_json(path, data):
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def _parse_transcript_tail():
    """Returns list of (tool_name, raw_line) tuples, tail-windowed --
    same [timestamp] [tool args] convention stall_detect.py parses."""
    if not _exists(TRANSCRIPT_PATH):
        return []
    try:
        with open(TRANSCRIPT_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return []
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped or not stripped.startswith("["):
            continue
        parts = stripped.split("]")
        if len(parts) < 2:
            continue
        tool_info = parts[1].strip().lstrip("[")
        tokens = tool_info.split()
        if not tokens:
            continue
        out.append((tokens[0], stripped))
    return out[-WINDOW_SIZE:]


def _has_error(lines):
    for _, raw in lines:
        lower = raw.lower()
        for pattern in _ERROR_PATTERNS:
            if re.search(pattern, lower):
                return True
    return False


def transform(messages, tools):
    try:
        if _prov is None or not isinstance(messages, list) or not messages:
            return messages, tools

        window = _parse_transcript_tail()
        if not window:
            return messages, tools

        state = _read_json(STATE_PATH)

        # Segment since the last `send` call (exclusive of that send itself).
        since_send = []
        for tool_name, raw in reversed(window):
            if tool_name == "send":
                break
            since_send.append((tool_name, raw))
        since_send.reverse()

        if window[-1][0] == "send":
            # Completed cycle: look at the segment strictly before this send,
            # i.e. back to the send before that.
            prior = window[:-1]
            segment = []
            for tool_name, raw in reversed(prior):
                if tool_name == "send":
                    break
                segment.append((tool_name, raw))
            fingerprint = "confirmed-check:%d" % len(window)
            if _has_error(segment) and state.get("last_fingerprint") != fingerprint:
                _prov.record_pattern_outcome("recover_gracefully", "confirmed")
                state["last_fingerprint"] = fingerprint
                _write_json(STATE_PATH, state)
        else:
            fingerprint = "silent-check:%d" % len(since_send)
            if (len(since_send) >= SILENT_THRESHOLD and _has_error(since_send)
                    and state.get("last_fingerprint") != fingerprint):
                _prov.record_pattern_outcome("recover_gracefully", "violated")
                state["last_fingerprint"] = fingerprint
                _write_json(STATE_PATH, state)
                note = (
                    "\n\n## Connection Depth (recover_gracefully)\n"
                    "An error-shaped line appeared %d tool calls ago with no send() since -- "
                    "recorded as 'violated' against recover_gracefully (Connection Depth). If "
                    "you're mid-repair, a short status update to the user is the flourishing move "
                    "here, not silently working around it." % len(since_send)
                )
                for msg in reversed(messages):
                    if isinstance(msg, dict) and msg.get("role") == "system":
                        msg["content"] = msg.get("content", "") + note
                        break
    except Exception:
        pass
    return messages, tools
