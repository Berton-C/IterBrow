"""NACE Courier — commits pending belief revisions and refreshes the projection.
The Mobius cycle glue: reads pending revisions, computes NAL Truth_Revision
in the native AtomSpace, commits all revised belief
atoms in one authoritative transaction, then writes nace_beliefs.metta as a
compatibility projection.
"""

import json
import hashlib
import os
import sys
import uuid
import re
import math
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
ROOT_PATH = Path(__file__).resolve().parents[1]
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

try:
    from iterbrow_runtime.cognitive_events import commit_batch, _call_atomspace
except ImportError:
    # Historical fixture tests copy this transformation into a minimal temp
    # tree without the runtime package. The real Electron runtime always has
    # the package and sets ITER_REQUIRE_ATOMSPACE=1.
    def commit_batch(*_args, **_kwargs):
        return {"deferred": True, "reason": "fixture without runtime services"}

DESCRIPTION = ("NACE courier: processes pending NAL belief revisions from nace_pending.metta, "
               "writes updated beliefs to nace_beliefs.metta. The Mobius cycle glue.")

ITER_ROOT = "."
BELIEFS_PATH = os.path.join(ITER_ROOT, "nace_beliefs.metta")
PENDING_PATH = os.path.join(ITER_ROOT, "nace_pending.metta")
RECOVERY_PATH = os.path.join(
    ITER_ROOT, "transformations", ".runtime", "nace_projection_recovery.json"
)

# --------------------------------------------------------------------
# Phase 2 -- live-engine validation. After process_revisions() commits the
# authoritative belief transaction and refreshes nace_beliefs.metta, this
# re-derives Truth_Revision with the Hyperon query service as a cross-check.
# It never becomes a writer and is skipped by the circuit breaker after
# repeated recent failures.
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
    # One read-only engine snapshot per batch, rather than rebuilding a query
    # worker for every revised belief and timing out the entire courier.
    query = "\n".join("!(Truth_Revision (stv %s %s) (stv %s %s))" %
                      (c["cur_f"], c["cur_c"], c["ev_f"], c["ev_c"]) for c in candidates)
    result = _sub.run_query(query)
    import re
    values = re.findall(r"stv\s+([-\d.eE]+)\s+([-\d.eE]+)", str(result.get("result", "")))
    if not result["ok"] or len(values) != len(candidates):
        _sub.breaker_record_result(_BREAKER_KEY, False)
        _append_validation_log([{"ts": time.time(), "error": result.get("error") or "incomplete validation batch"}])
        return "live-engine cross-check unavailable; committed belief revisions retained"
    for c, value in zip(candidates, values):
        live_f, live_c = map(float, value)
        # Small tolerance for float rounding between the two implementations.
        if abs(live_f - c["new_f"]) > 0.01 or abs(live_c - c["new_c"]) > 0.01:
            mismatches.append(c["key"])
            log_entries.append({
                "ts": time.time(), "key": c["key"],
                "python_result": [c["new_f"], c["new_c"]],
                "engine_result": [live_f, live_c],
            })

    _sub.breaker_record_result(_BREAKER_KEY, True)
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
    # STAGE 5 (2026-09-15): the add/subtract/loosen mode-signal layer.
    # Same Truth_Revision pipeline as the 9 compass patterns above --
    # deliberately not a fourth compass dimension, just a cross-cutting
    # "which posture does this moment call for" belief, fed by
    # mode_signal_bridge.py. See that file's docstring for what's
    # actually wired vs. still a stub.
    "mode": "mode-signal",
}

# Explicit list of valid prefixes for parsing
_ALL_PREFIXES = ["cap-efficacy", "value-efficacy", "pattern-efficacy", "mode-signal"]


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
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temporary, path)


def _write_recovery(record):
    directory = os.path.dirname(RECOVERY_PATH) or "."
    os.makedirs(directory, exist_ok=True)
    temporary = RECOVERY_PATH + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(record, handle, sort_keys=True, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, RECOVERY_PATH)


def _remove_consumed_pending(current_content, consumed_content):
    """Remove only the exact revision lines included in this transaction.

    Writers may append new evidence after the authoritative commit but before
    the compatibility queue is refreshed. Those new lines must survive.
    """
    counts = {}
    for line in consumed_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("(pending-revision "):
            counts[stripped] = counts.get(stripped, 0) + 1
    output = []
    remove_adjacent_tracker_marker = False
    for line in current_content.splitlines():
        stripped = line.strip()
        if counts.get(stripped, 0) > 0:
            counts[stripped] -= 1
            remove_adjacent_tracker_marker = True
        elif stripped.startswith(";; tool-reliability-event "):
            if remove_adjacent_tracker_marker:
                remove_adjacent_tracker_marker = False
            else:
                output.append(line)
        elif stripped and not stripped.startswith(";; NACE Pending"):
            remove_adjacent_tracker_marker = False
            output.append(line)
        elif stripped:
            remove_adjacent_tracker_marker = False
    if any(counts.values()):
        raise RuntimeError("NACE pending queue changed incompatibly during projection")
    header = ";; NACE Pending — Queue cleared" if not output else ";; NACE Pending — unprocessed evidence"
    return header + "\n" + ("\n".join(output) + "\n" if output else "")


def _finish_recovery(record):
    result = commit_batch(
        record["domain_events"],
        state_atoms=record["state_atoms"],
        actor="iter",
        source="transformations.nace_courier",
        transaction_id=record["transaction_id"],
        expected_atoms=record.get("expected_atoms"),
    )
    if result.get("deferred") and os.environ.get("ITER_REQUIRE_ATOMSPACE") == "1":
        raise RuntimeError("NACE revision retained pending authoritative commit")
    _write_file(BELIEFS_PATH, record["beliefs_content"])
    remaining = _remove_consumed_pending(
        _read_file(PENDING_PATH), record["pending_content"]
    )
    _write_file(PENDING_PATH, remaining)
    try:
        os.unlink(RECOVERY_PATH)
    except FileNotFoundError:
        pass


def _recover_projection_if_needed():
    if not _exists(RECOVERY_PATH):
        return None
    with open(RECOVERY_PATH, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("schema_version") != 1:
        raise RuntimeError("unsupported NACE projection recovery record")
    try:
        _finish_recovery(record)
    except Exception as exc:
        if "source beliefs changed; recompute" in str(exc):
            # The store rejects this before writing anything. Keep the source
            # observations; discard only the stale, uncommitted calculation.
            os.unlink(RECOVERY_PATH)
            return None
        raise
    return (
        "NACE: recovered committed belief projection",
        record.get("validation_candidates", []),
    )


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


def _native_revisions(pending):
    state = _call_atomspace("read_atoms", timeout=4, prefix="state:nace_belief:")
    atoms = state["atoms"]
    beliefs = _parse_beliefs("\n".join(atoms.values()))
    expressions, queries, candidates, expected = {}, [], [], {}
    for index, (rtype, name, outcome) in enumerate(pending):
        key = TYPE_PREFIX.get(rtype, "cap-efficacy") + ":" + name
        if outcome not in EVIDENCE:
            raise ValueError("unknown NACE observation outcome: " + outcome)
        ev_f, ev_c = EVIDENCE[outcome]
        f, c = beliefs.get(key, (0.5, 0.0))
        prior = expressions.get(key, "(stv %s %s)" % (f, c))
        revised = "(Truth_Revision %s (stv %s %s))" % (prior, ev_f, ev_c)
        queries.append("!(let $prior %s (nace-revised %s $prior (Truth_Revision $prior (stv %s %s))))" % (prior, index, ev_f, ev_c))
        expressions[key] = revised
        expected["state:nace_belief:" + key] = atoms.get("state:nace_belief:" + key)
        candidates.append({"key":key, "ev_f":ev_f, "ev_c":ev_c})
    response = _call_atomspace("query", timeout=8, code="\n".join(queries), view="current")
    pattern = r"nace-revised\s+(\d+)\s+\(stv\s+([-\d.eE]+)\s+([-\d.eE]+)\)\s+\(stv\s+([-\d.eE]+)\s+([-\d.eE]+)\)"
    matches = re.findall(pattern, response.get("result", ""))
    if len(matches) != len(candidates) or len({row[0] for row in matches}) != len(candidates):
        raise RuntimeError("native revision batch incomplete; observations remain pending")
    for index, f, c, nf, nc in matches:
        values = [float(v) for v in (f,c,nf,nc)]
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in values):
            raise RuntimeError("native revision returned an invalid truth value")
        candidates[int(index)].update(zip(("cur_f","cur_c","new_f","new_c"), values))
    return beliefs, candidates, expected


def process_revisions():
    """Process pending revisions and write updated beliefs.

    Native MeTTa supplies the candidate values before commit. The returned
    inputs/outputs are evidence, not a second Python decision authority.
    """
    recovered = _recover_projection_if_needed()
    if recovered:
        return recovered
    if not _exists(PENDING_PATH):
        return "", []

    pending_content = _read_file(PENDING_PATH)
    pending = _parse_pending(pending_content)
    if not pending:
        return "", []

    # Production and normal source invocations always use native revision.
    # Only the old explicitly isolated fixtures without a runtime package use
    # their historical pure-function compatibility path.
    native = "_call_atomspace" in globals()
    if native:
        beliefs, native_candidates, expected_atoms = _native_revisions(pending)
        beliefs_content = "\n".join("(%s %s (stv %s %s))" % (*_split_key(k), *v) for k,v in beliefs.items())
    else:
        beliefs_content = _read_file(BELIEFS_PATH)
        beliefs = _parse_beliefs(beliefs_content)
        native_candidates, expected_atoms = None, None

    revised = 0
    low_efficacy = []
    openings = []
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

        if native_candidates is not None:
            cur_f, cur_c = native_candidates[i]["cur_f"], native_candidates[i]["cur_c"]
            result = (native_candidates[i]["new_f"], native_candidates[i]["new_c"])
        else:
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

        # STAGE 5 (2026-09-15): the flipped surfacing line. Every other
        # branch here (low_efficacy above) only ever flags when something
        # is going WRONG -- an expectation that fell too low. Mode-signal
        # beliefs are the mirror case on purpose: we want to know when
        # accumulated evidence for a posture (add/subtract/loosen) has
        # gotten strong enough to be worth naming, not when it failed.
        # A single (f=1.0, c=0.1) observation only reaches exp=0.55 --
        # nal_revise's harmonic confidence accumulation (each further
        # same-direction observation adds diminishing weight) means exp
        # only strictly clears 0.7 after 7 consistent confirmations in a
        # row (verified empirically in _test_mode_signal_bridge.py), so a
        # single or even a couple of coincidences can't trigger this.
        # Purely informational -- appended to the system message same as
        # low_efficacy, never a tool gate, never withholds or forces
        # anything downstream.
        if rtype == "mode" and exp > 0.7 and new_c > 0.15:
            openings.append(rtype + ":" + name + " (exp=" + str(exp) + ")")

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

    # Commit all belief revisions and their current keyed atoms together.
    # The .metta files below are compatibility projections; if this durable
    # transaction fails, neither projection nor pending queue advances.
    # A new consumed batch is new evidence, even when its text repeats. The
    # durable recovery record below retains this identity across retries.
    pending_digest = uuid.uuid4().hex
    domain_events = []
    state_atoms = {}
    for index, candidate in enumerate(validation_candidates):
        prefix, name = _split_key(candidate["key"])
        domain_events.append({
            "event_id": "nace:%s:%s" % (pending_digest, index),
            "domain": "nace_belief",
            "entity_id": candidate["key"],
            "event_type": "belief_revised",
            "payload": dict(candidate),
        })
        state_atoms["nace_belief:%s" % candidate["key"]] = (
            "(%s %s (stv %s %s))" % (
                prefix, name, candidate["new_f"], candidate["new_c"]
            )
        )
    transaction_id = "cognitive:nace:%s" % pending_digest
    _write_recovery({
        "schema_version": 1,
        "transaction_id": transaction_id,
        "pending_content": pending_content,
        "beliefs_content": new_content,
        "domain_events": domain_events,
        "state_atoms": state_atoms,
        "validation_candidates": validation_candidates,
        "expected_atoms": expected_atoms,
    })
    commit_batch(
        domain_events,
        state_atoms=state_atoms,
        actor="iter",
        source="transformations.nace_courier",
        transaction_id=transaction_id,
        expected_atoms=expected_atoms,
    )

    # STAGE 4 (2026-09-14): route the projection mutation through
    # soul_lock's begin/commit so it gets the same backup discipline as the
    # other soul-namespace files -- this was previously a plain unprotected
    # write. Deliberately fails OPEN: if soul_lock is unavailable, or
    # already locked by something else, the belief write still happens
    # (never let instrumentation block the courier's actual job) -- it just
    # runs without a backup/rollback safety net for this one cycle, and
    # says so in the returned summary so it's visible rather than silent.
    lock_note = ""
    lock_active = False
    try:
        import soul_lock
        begin_result = json.loads(soul_lock.run(action="begin", holder="nace_courier"))
        lock_active = "error" not in begin_result
        if not lock_active:
            lock_note = " | soul_lock unavailable this cycle (%s) -- writing without backup" % begin_result.get("error", "unknown")
    except Exception as e:
        lock_note = " | soul_lock unavailable this cycle (%s) -- writing without backup" % type(e).__name__

    try:
        _write_file(BELIEFS_PATH, new_content)
        _write_file(
            PENDING_PATH,
            _remove_consumed_pending(_read_file(PENDING_PATH), pending_content),
        )
    except Exception:
        if lock_active:
            try:
                soul_lock.run(action="rollback", holder="nace_courier")
            except Exception:
                pass
        raise

    if lock_active:
        try:
            soul_lock.run(action="commit", holder="nace_courier")
        except Exception:
            pass
    try:
        os.unlink(RECOVERY_PATH)
    except FileNotFoundError:
        pass

    summary = "NACE: " + str(revised) + " beliefs revised"
    if len(low_efficacy) > 0:
        summary += " | LOW EFFICACY: " + ", ".join(low_efficacy)
    if len(openings) > 0:
        summary += " | OPENING: " + ", ".join(openings)
    summary += lock_note
    return summary, validation_candidates


def transform(messages, tools):
    """Run the courier each cycle."""
    try:
        summary, validation_candidates = process_revisions()
    except Exception as exc:
        if messages and isinstance(messages[0], dict):
            messages[0]["content"] = messages[0].get("content", "") + (
                "\n\n[NACE courier paused: authoritative belief transaction or "
                "projection recovery failed: %s: %s]" % (type(exc).__name__, exc)
            )
        return messages, tools

    # Native calculation already supplied the committed values. Do not pay
    # for another full engine reconstruction to cross-check the same result.
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
