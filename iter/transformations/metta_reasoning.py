"""MeTTa reasoning substrate -- Phase 1 (pre-decision symbolic summary).

Runs once per turn, before the LLM call. Loads nace_substrate.metta's NAL
formulas together with nace_beliefs.metta's live efficacy/calibration state
into a fresh, safety-bounded MeTTa space, evaluates the efficacy expectation
for each tool currently on offer, and appends a short symbolic summary to
the system message -- the same "[note]" pattern nace_courier.py already uses
for its belief-revision summary.

This is intentionally read-only: it never writes nace_beliefs.metta (that
stays nace_courier.py's job) and never blocks or vetoes anything (that is
tools/_metta_gate.py's job, wired in separately and only active in "enforce"
mode). If the reasoning substrate errors, times out, or the circuit breaker
is open, this transformation silently leaves messages/tools unchanged --
exactly like every other transformation in this pipeline degrades on
failure.

QUERY DESIGN NOTE: uses a direct `(match &self (cap-efficacy $cap $stv) ...)`
per tool rather than calling nace_substrate.metta's own should-dispatch/
current-efficacy directly -- those have a generic (stv 0.5 0.0) fallback
equation that overlaps with the real-belief equation, so MeTTa (which
returns every matching equation, not just the first) answers a direct
should-dispatch query ambiguously (both the real and the fallback result at
once). Querying cap-efficacy facts directly avoids that ambiguity and also
gives an unambiguous "no data yet" case (empty result) for tools with no
calibration history, which this transformation reports as such rather than
guessing.

Safety: this whole call runs inside its own iter.py invoke_dynamic()
subprocess and inherits its wall-clock timeout + hard process-group kill.
tools/_metta_substrate.py additionally runs a portable memory watchdog
(RSS-polling, since setrlimit is not enforced on macOS) around the actual
MeTTa evaluation, and a circuit breaker skips this pass entirely after
repeated recent failures.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import _metta_substrate as _sub  # noqa: E402

DESCRIPTION = (
    "Runs a bounded MeTTa reasoning pass over nace_substrate.metta + "
    "nace_beliefs.metta each turn and appends a short symbolic summary "
    "(efficacy expectation for the tools on offer this turn) to the system "
    "message. Read-only and fail-open: never writes beliefs, never blocks "
    "anything -- degrades silently on error."
)

_KB_FILE = "kb_substrate.metta"
_TASKS_FILE = "memory/tasks/current_tasks.txt"


def _kb_context_atom():
    """human_present vs human_absent, from the active task's person field."""
    try:
        with open(_TASKS_FILE, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("# Person:"):
                    person = line.split(":", 1)[1].strip().lower()
                    return "human_present" if person == "user" else "human_absent"
    except Exception:
        return None
    return None


def _kb_verdict_summary(root=".", gate_go=0.7, gate_block=0.3):
    """One bounded, fail-open pass over kb_substrate.metta.

    Query design (lessons 0a9daf58 + 10479f78): rule application via
    pattern=antecedent/template=consequent; every verdict carries its own
    action name, so merged match outputs are regex-parseable without
    chunking. Read-only: asserts ONE fresh context atom into the throwaway
    evaluation space (never persisted to disk; run_query builds a fresh
    space per call). Any error returns "" -- KB section is simply omitted.
    """
    try:
        kb_path = os.path.join(root, _KB_FILE)
        with open(kb_path, "r", encoding="utf-8", errors="replace") as fh:
            kb_text = fh.read()
        if not kb_text.strip():
            return ""
        ctx = _kb_context_atom()
        if ctx is None:
            return ""
        query = "\n".join([
            "(--> iter ([] current_context %s))" % ctx,
            "!(match &self (--> $th ([] gate_go_threshold)) $th)",
            "!(match &self (--> $th ([] gate_block_threshold)) $th)",
            "!(match &self (--> $a ([] gate_score $f)) (--> $a ([] evaluate_action $f)))",
            "!(match &self (--> $ag ([] current_context %s)) (--> $ag ([] should %s)))" % (
                ctx, "serve_user" if ctx == "human_present" else "self_improve"),
        ])
        result = _sub.run_query(query, extra_facts=kb_text, root=root)
        _sub.breaker_record_result("kb_consumer", result["ok"])
        if not result["ok"]:
            return ""
        text = result["result"]
        m_go = re.search(r"([0-9.]+)\s*\[\]\s*gate_go_threshold", text)
        m_bl = re.search(r"([0-9.]+)\s*\[\]\s*gate_block_threshold", text)
        if m_go:
            gate_go = float(m_go.group(1))
        if m_bl:
            gate_block = float(m_bl.group(1))
        verdicts = []
        seen = {}
        for name, score in re.findall(r"(\w+)\s*\(\[\]\s*evaluate_action\s+([0-9.eE+-]+)", text):
            s = float(score)
            prev = seen.get(name)
            if prev is None or s > prev:
                seen[name] = s
        for name, s in sorted(seen.items()):
            if s > gate_go:
                v = "go"
            elif s < gate_block:
                v = "blocked"
            else:
                v = "review"
            verdicts.append("%s %s=%.2f" % (name, v, s))
        m_pr = re.search(r"\[\]\s*should\s+(\w+)", text)
        parts = []
        if verdicts:
            parts.append("gate: " + ", ".join(verdicts))
        if m_pr:
            parts.append("priority: %s (%s)" % (m_pr.group(1), ctx))
        return ("substrate-KB " + "; ".join(parts)) if parts else ""
    except Exception:
        return ""



_PLAN_FILE = os.path.join(".runtime", "build_plan.metta")

def _plan_vet_summary(root="."):
    """Plan-time vetting (2026-09-20 build, user-approved): read the canonical
    plan file .runtime/build_plan.metta, derive per-step gate verdicts from the
    Layer-6 invariant scores BEFORE code exists, flag violations. Plan shape:
    (plan-step <id> <label>) + (--> <id> ([] <feature>)) flags. Fail-open:
    missing/empty/garbage plan or ANY error returns "" (section omitted)."""
    try:
        if not os.path.isfile(_PLAN_FILE):
            return ""
        with open(_PLAN_FILE, "r", encoding="utf-8", errors="replace") as fh:
            plan_text = fh.read()
        if not plan_text.strip():
            return ""
        kb_path = os.path.join(root, _KB_FILE)
        with open(kb_path, "r", encoding="utf-8", errors="replace") as fh:
            kb_text = fh.read()
        m_ep = re.search(r"\(plan-epoch (\S+?)\)", plan_text)
        if not m_ep:
            return ""  # plan without epoch = unparsable shape -> fail open
        epoch = m_ep.group(1)
        feats = re.findall(r"\(inv-feature-score (\w+) \(stv", kb_text)
        if not feats:
            return ""
        # Epoch-scoped flags: steps are PAIRS (step epoch) so stale plan atoms
        # from previous turns (persistent shared space) carry old epochs and
        # are structurally filtered out below (stale-leak fix, 18:47 test).
        q = ["!(match &self (inv-feature-score $feat (stv $f $c)) (inv-score $feat $f))",
             "!(match &self (inv-feature-invariant $f $inv) (inv-map $f $inv))"]
        q += ["!(match &self (--> ($s $e) ([] %s)) (--> ($s $e) ([] flag %s)))" % (f, f) for f in feats]
        result = _sub.run_query("\n".join(q), extra_facts=kb_text + "\n" + plan_text, root=root)
        _sub.breaker_record_result("kb_consumer", result["ok"])
        if not result["ok"]:
            return ""
        text = result["result"]
        scores = {}
        for name, s in re.findall(r"inv-score\s+\(?\s*(\w+)\s*\)?\s*([0-9.eE+-]+)", text):
            scores[name] = float(s)
        if not scores:
            return ""
        invmap = dict(re.findall(r"inv-map\s+\(?\s*(\w+)\s*\)?\s*(\w+)", text))
        steps = {}
        for step, ep, feat in re.findall(r"\(\s*(\w+) ([\w.:T-]+)\)\s*\(\[\]\s*flag\s+(\w+)", text):
            if ep == epoch:  # drop rows from any earlier plan (stale space atoms)
                steps.setdefault(step, []).append(feat)
        if not steps:
            return ""
        if not steps:
            return ""  # only stale rows matched -> no current-plan evidence, omit
        out = []
        for step in sorted(steps):
            fs = [(f, scores.get(f, 0.5)) for f in steps[step]]
            f, s = min(fs, key=lambda x: x[1])
            if s > 0.7:
                v = "go"
            elif s < 0.3:
                v = "BLOCKED"
            else:
                v = "review"
            out.append("%s %s=%.2f (%s)" % (step, v, s, invmap.get(f, f)))
        n_block = sum(1 for o in out if " BLOCKED" in o)
        return "plan-vet(%d steps): %s" % (len(out), ", ".join(out))
    except Exception:
        return ""

_BREAKER_KEY = "reasoning_pass"
# FIX 2026-09-20 (timeout): the MeTTa batch cost is ~1.2s PER TOOL
# (12 tools ~= 14-15s, which blew iter.py's 15s wall clock in live cycles;
# offline single tests at 5 tools / 5.8s under-represented the live 12-tool
# case). Cap at 8 tools (~9.5s worst case) to leave headroom under the 15s
# subprocess timeout, and truncate the tool list if more are on offer.
_MAX_TOOLS_CHECKED = 8  # keep the generated MeTTa program small/bounded AND under the 15s wall clock
_THRESHOLD = 0.3


def _tool_names(tools):
    names = []
    for t in list(tools or [])[:_MAX_TOOLS_CHECKED]:
        try:
            name = t.get("function", {}).get("name")
        except AttributeError:
            name = None
        if name:
            cleaned = "".join(ch for ch in str(name) if ch.isalnum() or ch == "_")
            if cleaned:
                names.append(cleaned)
    return names


def _parse_batch_result(result_text, names):
    """result_text looks like '[[Grounded(0.29)], [Grounded(0.96)], []]' --
    one bracketed group per query, in the same order names were queried."""
    # FIX 2026-09-20: the MeTTa kernel merges ALL per-query match outputs into
    # ONE flat list of values with no separators between queries (batch of 3
    # tools returned 48 values = 16 formulas each, in query order). The old
    # innermost-bracket regex assumed one bracketed group per query, so every
    # multi-tool batch silently parsed to None. Robust parse: flatten every
    # number, then chunk the flat list equally among the queries. Within one
    # tool all matched formulas carry the same Truth_Expectation value, so
    # equal chunking is safe whenever the total is divisible; if not divisible
    # (unexpected), fall back to None per tool rather than guessing.
    nums = re.findall(r"[-]?\d+\.\d+(?:[eE][-+]?\d+)?", result_text)
    if not nums:
        return {n: None for n in names}
    if len(nums) % len(names) == 0:
        chunk = len(nums) // len(names)
        return {
            n: float(nums[i * chunk])
            for i, n in enumerate(names)
        }
    return {n: None for n in names}


def transform(messages, tools):
    if _sub.breaker_should_skip(_BREAKER_KEY):
        return messages, tools

    names = _tool_names(tools)
    if not names:
        return messages, tools

    query = "\n".join(
        "!(match &self (cap-efficacy %s $stv) (Truth_Expectation $stv))" % n for n in names
    )
    result = _sub.run_query(query)
    _sub.breaker_record_result(_BREAKER_KEY, result["ok"])
    if not result["ok"]:
        return messages, tools

    expectations = _parse_batch_result(result["result"], names)
    low = [n for n, e in expectations.items() if e is not None and e < _THRESHOLD]
    unknown_count = sum(1 for e in expectations.values() if e is None)

    parts = []
    if low:
        parts.append("below should-dispatch threshold (%.2f): %s" % (_THRESHOLD, ", ".join(low)))
    if unknown_count:
        parts.append("%d tool(s) with no calibration data yet" % unknown_count)
    if not parts:
        parts.append("all %d checked tools currently above threshold" % len(names))

    kb = _kb_verdict_summary()
    if kb:
        parts.append(kb)
    pv = _plan_vet_summary()
    if pv:
        parts.append(pv)

    summary = "[NACE reasoning pass: " + "; ".join(parts) + "]"
    for message in messages:
        if message.get("role") == "system":
            message["content"] = message.get("content", "") + "\n\n" + summary
            break

    return messages, tools
