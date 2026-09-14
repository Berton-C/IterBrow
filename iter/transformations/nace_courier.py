"""NACE Courier â processes pending belief revisions and writes back to nace_beliefs.metta.
The Mobius cycle glue: reads pending revisions, computes NAL Truth_Revision
in Python (same formula as the MeTTa substrate), writes updated beliefs back.
Uses pure string parsing for MicroPython compatibility.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))

DESCRIPTION = ("NACE courier: processes pending NAL belief revisions from nace_pending.metta, "
               "writes updated beliefs to nace_beliefs.metta. The Mobius cycle glue.")

ITER_ROOT = "."
BELIEFS_PATH = os.path.join(ITER_ROOT, "nace_beliefs.metta")
PENDING_PATH = os.path.join(ITER_ROOT, "nace_pending.metta")

# --------------------------------------------------------------------
# Phase 2 -- live-engine validation (added; does not change any of the
# behavior above). Runs AFTER process_revisions() has already parsed,
# revised, and written nace_beliefs.metta -- order matters: the write is the
# authoritative, load-bearing action and must complete first, unaffected by
# anything that follows. This validation step re-derives the same NAL
# Truth_Revision result via the real pymetta engine (nace_substrate.metta's
# own Truth_Revision formula) for each revision this cycle, purely to check
# it agrees with the pure-Python reimplementation above, and logs any
# mismatch/error to a small capped diagnostics file. It never feeds its
# result back into beliefs, never raises out of transform(), and is skipped
# entirely (via the shared circuit breaker) after repeated recent failures.
# -------------------------------------------------------------------
VALIDATION_LOG_PATH = os.path.join(ITER_ROOT, "memory", "_metta_validation_log.json")
_VALIDATION_LOG_MAX_ENTRIES = 200
_BREAKER_KEY = "courier_validation"


def _append_validation_log(entries, path=None):
    import json
    path = path or VALIDATION_LOG_PATH
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        existing = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    existing = json.load(fh)
                if not isinstance(existing, list):
                    existing = []
            except Exception:
                existing = []
        existing.extend(entries)
        if len(existing) > _VALIDATION_LOG_MAX_ENTRIES:
            existing = existing[-_VALIDATION_LOG_MAX_ENTRIES:]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(existing, fh)
    except Exception:
        pass  # diagnostics-only; never let logging failure matter


def validate_against_live_engine(candidates):
    """Best-effort, non-blocking. Re-runs Truth_Revision for each candidate
    through the real MeTTa engine and logs any disagreement with the
    pure-Python nal_revise() result above. Returns a short human string for
    the system-message note, or "" on any failure (never raises).
    """
    if not candidates:
        return ""
    try:
        import _metta_substrate as _sub
    except Exception:
        return ""

    if _sub.breaker_should_skip(_BREAKER_KEY):
        return ""

    import time
    mismatches = []
    log_entries = []
    any_ok = False
    for c in candidates:
        query = "!(Truth_Revision (stv %s %s) (stv %s %s))" % (c["cur_f"], c["cur_c"], c["ev_f"], c["ev_c"])
        result = _sub.run_query(query)
        if not result["ok"]:
            log_entries.append({"ts": time.time(), "key": c["key"], "error": result["error"]})
            continue
        any_ok = True
        live_f, live_c = _parse_stv(result["result"])
        if live_f is None:
            log_entries.append({"ts": time.time(), "key": c["key"], "error": "unparseable engine result: %s" % result["result"][:150]})
            continue
        # Small tolerance for float rounding between the two implementations.
        if abs(live_f - c["new_f"]) > 0.01 or abs(live_c - c["new_c"]) > 0.01:
            mismatches.append(c["key"])
            log_entries.append({
                "ts": time.time(), "key": c["key"],
                "python_result": [c["new_f"], c["new_c"]],
                "engine_result": [live_f, live_c],
            })

    _sub.breaker_record_result(_BREAKER_KEY, any_ok or not candidates)
    if log_entries:
        _append_validation_log(log_entries)

    if mismatches:
        return "live-engine validation flagged %d mismatch(es): %s" % (len(mismatches), ", ".join(mismatches))
    return ""


def _parse_stv(result_text):
    import re
    m = re.search(r"stv\s+([-\d.eE]+)\s+([-\d.eE]+)", str(result_text))
    if not m:
        return None, None
    try:
        return float(m.group(1)), float(m.group(2))
    except ValueError:
        return None, None

EVIDENCE = {
    "confirmed": (1.0, 0.1),
    "disconfirmed": (0.0, 0.1),
    "partial": (0.5, 0.05),
    "aligned": (1.0, 0.1),
    "violated": (0.0, 0.1),
    "conflicted": (0.5, 0.05),
}

TYPE_PREFIX = {
    "tool": "cap-efficacy",
    "value": "value-efficacy",
    "pattern": "pattern-efficacy",
}

# Explicit list of valid prefixes for parsing
_ALL_PREFIXES = ["cap-efficacy", "value-efficacy", "pattern-efficacy"]


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _weight(c):
    if c > 0 and c < 1.0:
        return c / (1 - c)
    if c >= 1.0:
        return 1e10
    return 0.0


def nal_revise(f1, c1, f2, c2):
    w1 = _weight(c1)
    w2 = _weight(c2)
    total = w1 + w2
    if total == 0:
        return (f2, c2)
    f_new = (w1 * f1 + w2 * f2) / total
    c_new = total / (total + 1)
    return (round(f_new, 4), round(c_new, 4))


def nal_expectation(f, c):
    return round(c * (f - 0.5) + 0.5, 4)


def _read_file(path):
    try:
        with open(path, "r") as fh:
            return fh.read()
    except Exception:
        return ""


def _write_file(path, content):
    try:
        with open(path, "w") as fh:
            fh.write(content)
    except Exception:
        pass


def _split_key(key):
    """Split 'prefix:name' into (prefix, name). Returns (prefix, name) or ('', '')."""
    ci = key.find(":")
    if ci < 0:
        return ("", key)
    return (key[:ci], key[ci + 1:])


def _parse_beliefs(content):
    """Parse beliefs into dict: {prefix:name: (f, c)}"""
    beliefs = {}
    lines = content.split("\n")
    for line in lines:
        line = line.strip()
        if len(line) < 5 or not line.startswith("("):
            continue
        if line.startswith(";;"):
            continue
        for prefix in _ALL_PREFIXES:
            tag = "(" + prefix + " "
            if line.startswith(tag):
                rest = line[len(tag):]
                pi = rest.find(" (stv ")
                if pi < 0:
                    break
                name = rest[:pi]
                sp = rest[pi + 6:]
                ci = sp.find("))")
                if ci < 0:
                    break
                nums = sp[:ci].strip()
                nparts = nums.split()
                if len(nparts) >= 2:
                    beliefs[prefix + ":" + name] = (float(nparts[0]), float(nparts[1]))
                break
    return beliefs


def _parse_pending(content):
    """Parse pending into list of [type, name, outcome]"""
    pending = []
    tag = "(pending-revision "
    lines = content.split("\n")
    for line in lines:
        line = line.strip()
        if not line.startswith(tag):
            continue
        rest = line[len(tag):]
        if rest.endswith(")"):
            rest = rest[:-1]
        parts = rest.strip().split()
        if len(parts) >= 3:
            pending.append([parts[0], parts[1], parts[2]])
    return pending


def process_revisions():
    """Process pending revisions and write updated beliefs.

    Returns (summary, validation_candidates) -- the second element is a list
    of dicts capturing each revision's inputs/outputs, for the Phase 2
    live-engine validation pass (see validate_against_live_engine above),
    which the caller runs strictly AFTER this function's write has already
    completed.
    """
    if not _exists(PENDING_PATH):
        return "", []

    pending_content = _read_file(PENDING_PATH)
    pending = _parse_pending(pending_content)
    if not pending:
        return "", []

    beliefs_content = _read_file(BELIEFS_PATH)
    beliefs = _parse_beliefs(beliefs_content)

    revised = 0
    low_efficacy = []
    validation_candidates = []

    # Get keys list for safe iteration
    belief_keys = list(beliefs.keys())

    for i in range(len(pending)):
        entry = pending[i]
        rtype = entry[0]
        name = entry[1]
        outcome = entry[2]

        prefix = TYPE_PREFIX.get(rtype, "cap-efficacy")
        key = prefix + ":" + name

        ev = EVIDENCE.get(outcome, (0.5, 0.05))
        ev_f = ev[0]
        ev_c = ev[1]

        if key in beliefs:
            cur = beliefs[key]
            cur_f = cur[0]
            cur_c = cur[1]
        else:
            cur_f = 0.5
            cur_c = 0.0

        result = nal_revise(cur_f, cur_c, ev_f, ev_c)
        new_f = result[0]
        new_c = result[1]
        beliefs[key] = (new_f, new_c)
        revised = revised + 1
        validation_candidates.append({
            "key": key, "cur_f": cur_f, "cur_c": cur_c,
            "ev_f": ev_f, "ev_c": ev_c, "new_f": new_f, "new_c": new_c,
        })

        exp = nal_expectation(new_f, new_c)
        if exp < 0.3 and new_c > 0.1:
            low_efficacy.append(rtype + ":" + name + " (exp=" + str(exp) + ")")

    # Rebuild beliefs file preserving structure
    if beliefs_content:
        lines = beliefs_content.split("\n")
        updated_lines = []
        replaced = set()
        all_keys = list(beliefs.keys())

        for line in lines:
            replaced_this = False
            for key in all_keys:
                sk = _split_key(key)
                prefix = sk[0]
                name = sk[1]
                tag = "(" + prefix + " " + name + " (stv"
                if tag in line and key not in replaced:
                    val = beliefs[key]
                    updated_lines.append(
                        "(" + prefix + " " + name + " (stv " +
                        str(val[0]) + " " + str(val[1]) + "))")
                    replaced.add(key)
                    replaced_this = True
                    break
            if not replaced_this:
                updated_lines.append(line)

        # Add new beliefs not already in file
        for key in all_keys:
            if key not in replaced:
                sk = _split_key(key)
                prefix = sk[0]
                name = sk[1]
                val = beliefs[key]
                updated_lines.append(
                    "(" + prefix + " " + name + " (stv " +
                    str(val[0]) + " " + str(val[1]) + "))")

        new_content = "\n".join(updated_lines)
    else:
        new_content = ";; NACE Beliefs\n"
        all_keys = list(beliefs.keys())
        for key in all_keys:
            sk = _split_key(key)
            prefix = sk[0]
            name = sk[1]
            val = beliefs[key]
            new_content += "(" + prefix + " " + name + " (stv " + \
                str(val[0]) + " " + str(val[1]) + "))\n"

    _write_file(BELIEFS_PATH, new_content)
    _write_file(PENDING_PATH, ";; NACE Pending â Queue cleared\n")

    summary = "NACE: " + str(revised) + " beliefs revised"
    if len(low_efficacy) > 0:
        summary += " | LOW EFFICACY: " + ", ".join(low_efficacy)
    return summary, validation_candidates


def transform(messages, tools):
    """Run the courier each cycle."""
    try:
        summary, validation_candidates = process_revisions()
    except Exception:
        return messages, tools

    # Phase 2: live-engine validation. Runs only AFTER process_revisions()
    # above has already written nace_beliefs.metta -- this is purely a
    # best-effort diagnostic on top, never able to affect the write that
    # already happened. Broadly guarded: any failure here is swallowed.
    validation_note = ""
    try:
        validation_note = validate_against_live_engine(validation_candidates)
    except Exception:
        validation_note = ""

    if summary:
        note = summary
        if validation_note:
            note += " | " + validation_note
        for i in range(len(messages)):
            if messages[i].get("role") == "system":
                messages[i]["content"] = messages[i]["content"] + "\n\n[" + note + "]"
                break
    return messages, tools
