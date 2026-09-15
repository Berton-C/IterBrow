"""Provenance Guard -- structurally checks newly-written code (via shell
heredocs or python open()-writes) for the two specific, mechanical failure
modes behind the 2026-09-14 beliefs_layer.html incident, and feeds real
support()/contradict() evidence into the previously-dormant
verify_before_claiming NAL pattern.

THE INCIDENT THIS GENERALIZES FROM: a script (refresh_beliefs_fc.py) was
written to fix a stale dashboard, but (1) it lived at iter/ root instead of
transformations/, so iter.py's loader (which only globs transformations/*.py)
never once invoked it, and (2) it read metadata["stv"], a key that
tools/support.py and tools/contradict.py never write -- they write
metadata["strength"] and metadata["confidence"] separately -- so even a
manual run would have silently zeroed out every meter. Three days passed
before a human caught it, not the system.

LEVERAGE, NOT A KEYWORD LIST: the fix on the table originally was to scan
new file content for future-conditional promise phrasing ("will re-render
once...", "is wired to..."). Rejected as a long-tail bandaid -- infinite
ways to phrase an ungrounded claim, but exactly one thing that's actually
true or false underneath any of them. This checks that one thing directly,
via tools/_provenance.py's two structural primitives:

  1. misplaced_hook_reason -- does this new file look like a
     transformation/tool hook (transform()/run() + DESCRIPTION) yet live
     outside the directories iter.py's own loader actually scans?
  2. unproduced_keys        -- does this new file read a metadata/JSON key
     that no other file in the whole repo ever writes?

Both are mechanical facts about the code itself, independent of anything
the model said about it in chat or in a page footer -- so there is no
English phrasing to catch and no long tail to chase.

MECHANISM: each cycle, scans `messages` for shell/python tool calls that
write new file content (heredoc `cat > path <<EOF` / `cat <<EOF > path`,
or python `open(path, \"w\")` + a nearby triple-quoted literal -- the
python extraction is a best-effort fallback, not a real parser, and can
miss content built from variables/concatenation; documented limitation,
not silently assumed reliable). Each (path, content) pair not already
resolved (tracked by tool_call id in PROVENANCE_STATE_PATH, so nothing is
judged twice) is run through both checks. A flag on either axis is a real
`violated` observation; a governed-dir write or metadata-touching write
that passes both clean is a real `confirmed` observation. Both are
appended to nace_pending.metta -- the SAME queue every other belief
revision in this app already flows through (nace_courier.py) -- exactly
mirroring idle_cycle_detector.py's established convention of planting
observations into reasoning that already exists, rather than growing an
orphan belief only this file understands.

`verify_before_claiming` is an EXISTING compass pattern already declared in
nace_beliefs.metta (stv 0.5 0.2, a frozen prior). Before this file, of the
9 declared compass patterns only `prioritize_user` (via
idle_cycle_detector.py) ever received a single real support/contradict
event. This closes that gap for the pattern most directly relevant to the
incident above.

ENFORCEMENT IS OBSERVE-FIRST: a violation appends one advisory note to the
system message (mirroring completion_claim_guard's note style) but does
NOT withhold `send` the way that guard does. The python-write extraction
in particular is a known-imperfect heuristic; withholding send is deferred
until verify_before_claiming's own tracked confidence -- now, for the
first time, built from real cycles instead of a guess -- says this
detector's positive-flag rate has earned that.

Fails open on any error -- never blocks dispatch, never raises out of
transform().
"""
import os
import re
import sys
import json
import hashlib

_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
try:
    import _provenance as _prov
except Exception:
    _prov = None

DESCRIPTION = "Detects governed-directory code writes that are misplaced (won't be auto-loaded) or reference metadata keys nothing in the repo ever produces, and feeds real support/contradict events into the previously-dormant verify_before_claiming NAL pattern"

STATE_PATH = os.path.join("memory", ".provenance_guard_state.json")
STATE_MAX_ENTRIES = 500

_HEREDOC_PATTERNS = [
    re.compile(
        r"cat\s*>\s*(?P<path>[^\s<>|;]+)\s*<<\s*['\"]?(?P<delim>\w+)['\"]?\s*\n"
        r"(?P<body>.*?)\n\s*(?P=delim)\b",
        re.DOTALL,
    ),
    re.compile(
        r"cat\s*<<\s*['\"]?(?P<delim>\w+)['\"]?\s*>\s*(?P<path>[^\s<>|;]+)\s*\n"
        r"(?P<body>.*?)\n\s*(?P=delim)\b",
        re.DOTALL,
    ),
]
_PY_OPEN_WRITE_RE = re.compile(r"open\(\s*['\"](?P<path>[^'\"]+)['\"]\s*,\s*['\"]w")
_PY_TRIPLE_STRING_RE = re.compile(r"(?:'''|\"\"\")(?P<body>.*?)(?:'''|\"\"\")", re.DOTALL)


def _extract_shell_writes(cmd):
    out = []
    for pat in _HEREDOC_PATTERNS:
        for m in pat.finditer(cmd):
            out.append((m.group("path"), m.group("body")))
    return out


def _extract_python_writes(code):
    out = []
    for m in _PY_OPEN_WRITE_RE.finditer(code):
        body_m = _PY_TRIPLE_STRING_RE.search(code)
        if body_m:
            out.append((m.group("path"), body_m.group("body")))
    return out


def _tool_call_text(call):
    try:
        fn = call.get("function", {}) if isinstance(call, dict) else {}
        name = fn.get("name", "")
        args = fn.get("arguments", "")
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
            except Exception:
                parsed = None
        else:
            parsed = args
        if name == "shell":
            raw = parsed.get("cmd", "") if isinstance(parsed, dict) else str(args)
            return "shell", raw
        if name == "python":
            raw = parsed.get("code", "") if isinstance(parsed, dict) else str(args)
            return "python", raw
        return None, None
    except Exception:
        return None, None


def _call_id(msg_index, call):
    try:
        cid = call.get("id") if isinstance(call, dict) else None
    except Exception:
        cid = None
    if cid:
        return str(cid)
    try:
        raw = json.dumps(call, sort_keys=True, default=str)
    except Exception:
        raw = str(call)
    return "h" + hashlib.sha1((str(msg_index) + raw).encode("utf-8", "replace")).hexdigest()[:16]


def _find_writes(messages):
    """Yield (call_id, path, content) for each new-file write found in any
    assistant shell/python tool call."""
    out = []
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        for call in (msg.get("tool_calls") or []):
            kind, text = _tool_call_text(call)
            if not kind or not text:
                continue
            pairs = _extract_shell_writes(text) if kind == "shell" else _extract_python_writes(text)
            for (path, content) in pairs:
                out.append((_call_id(i, call), path, content))
    return out


def _relevant(path, content):
    """Only worth judging when the write is either governed-dir-shaped
    (hook risk applies) or metadata/JSON-touching (contract risk applies).
    Ordinary file writes (docs, configs unrelated to either axis) are
    skipped entirely so they don't dilute confirmed/violated counts with
    noise neither check was designed to speak to."""
    if _prov is None:
        return False
    if _prov.looks_like_hook(content):
        return True
    return _prov.touches_shared_state(content)


def transform(messages, tools):
    try:
        if _prov is None or not isinstance(messages, list) or not messages:
            return messages, tools

        writes = _find_writes(messages)
        if not writes:
            return messages, tools

        try:
            with open(STATE_PATH, "r", encoding="utf-8") as fh:
                state = json.load(fh)
            if not isinstance(state, dict) or not isinstance(state.get("processed"), list):
                state = {"processed": []}
        except Exception:
            state = {"processed": []}
        processed = set(state.get("processed", []))

        newly = []
        violations = []
        confirmed_count = 0

        for (call_id, path, content) in writes:
            if call_id in processed:
                continue
            if not _relevant(path, content):
                continue
            newly.append(call_id)
            reasons = []
            hook_reason = _prov.misplaced_hook_reason(path, content)
            if hook_reason:
                reasons.append(hook_reason)
            bad_keys = _prov.unproduced_keys(content, exclude_path=path)
            if bad_keys:
                reasons.append(
                    "%r reads key(s) %s via .get()/[] that no other file in the repo ever "
                    "writes -- same shape as the 'stv' bug (support.py/contradict.py write "
                    "strength/confidence, never stv)." % (path, ", ".join(bad_keys))
                )
            if reasons:
                violations.append((path, reasons))
                _prov.record_pattern_outcome("verify_before_claiming", "violated")
            else:
                confirmed_count += 1
                _prov.record_pattern_outcome("verify_before_claiming", "confirmed")

        if not newly:
            return messages, tools

        state["processed"] = list(processed) + newly
        if len(state["processed"]) > STATE_MAX_ENTRIES:
            state["processed"] = state["processed"][-STATE_MAX_ENTRIES:]
        try:
            d = os.path.dirname(STATE_PATH)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(STATE_PATH, "w", encoding="utf-8") as fh:
                json.dump(state, fh)
        except Exception:
            pass

        if violations:
            detail_lines = []
            for path, reasons in violations:
                for r in reasons:
                    detail_lines.append("- " + r)
            note = (
                "\n\n## Provenance Guard\n"
                "A code write this session failed a structural check before it was ever run:\n"
                + "\n".join(detail_lines) + "\n"
                "Recorded as a real 'violated' observation against the verify_before_claiming "
                "pattern (nace_pending.metta -> nace_beliefs.metta via the normal courier "
                "cycle) -- this is the exact shape of the 2026-09-14 beliefs_layer.html "
                "incident (wrong directory, wrong field name), not a hypothetical. Fix the "
                "path/interface before claiming this works."
            )
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "system":
                    msg["content"] = msg.get("content", "") + note
                    break
    except Exception:
        pass
    return messages, tools
