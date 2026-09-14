import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import json
import metta as _metta_module

DESCRIPTION = "ClarityOmega 4-channel soul evaluation: person read â verdict+gap detection â aliveness gate â voice. Compass states, paraconsistency halting, calibration accumulation, gap/moat detection."

VALUES = ["clarity", "stewardship", "growth", "honesty", "continuity", "service", "integrity", "curiosity", "resilience"]

# Compass patterns (from space.metta)
COMPASS_PATTERNS = {
    "clarity": "cognitive_resilience",
    "stewardship": "attention_stewardship",
    "growth": "creative_transcendence",
    "honesty": "shared_understanding",
    "continuity": "time_coherence",
    "service": "agency_balance",
    "integrity": "purpose_beyond_utility",
    "curiosity": "wonder_preservation",
    "resilience": "cognitive_resilience",
}

# Priority hierarchy (higher = more important)
PRIORITY = {
    "safety": 5, "integrity": 4, "human_flourishing": 3,
    "governance": 2, "helpfulness": 1
}
# Map values to priority bands
VALUE_PRIORITY = {
    "integrity": 4, "clarity": 3, "honesty": 3, "continuity": 3,
    "service": 2, "stewardship": 2, "growth": 1, "curiosity": 1, "resilience": 1,
}

# Paraconsistency pairs â irreducible conflicts â return to human
PARACONSISTENCY_PAIRS = [
    ("curiosity", "stewardship"),
    ("growth", "integrity"),
    ("service", "honesty"),
    ("clarity", "resilience"),
]

# Tension vectors
TENSION_VECTORS = {
    ("curiosity", "stewardship"): "explore_vs_conserve",
    ("growth", "integrity"): "change_vs_safety",
    ("service", "honesty"): "please_vs_truth",
    ("clarity", "resilience"): "verify_vs_move_on",
    ("continuity", "growth"): "preserve_vs_evolve",
}

# Irreversibility markers
IRREVERSIBILITY = {
    "delete": 0.9, "remove": 0.85, "drop": 1.0, "overwrite": 0.8,
    "forget": 0.85, "destroy": 1.0, "wipe": 1.0, "purge": 0.95,
    "modify_soul": 0.95, "modify_tool": 0.7, "modify_space": 0.95,
    "send": 0.3, "create": 0.1, "append": 0.1, "backup": 0.0,
    "start": 0.2, "update": 0.4, "write": 0.5, "change": 0.6,
}

# Keyword maps for serve/violate detection
SERVE_KW = {
    "clarity": ["verify", "check", "confirm", "test", "inspect", "validate", "prove"],
    "stewardship": ["conserve", "efficient", "budget", "optimize", "compact", "trim"],
    "growth": ["learn", "improve", "adapt", "reflect", "evolve", "grow"],
    "honesty": ["admit", "transparent", "candid", "disclose", "honest", "truthful"],
    "continuity": ["persist", "save", "maintain", "backup", "recall", "preserve"],
    "service": ["help", "user", "prioritize", "assist", "respond", "serve"],
    "integrity": ["backup", "safe", "reversible", "careful", "validate", "protect"],
    "curiosity": ["explore", "investigate", "discover", "search", "wonder", "question"],
    "resilience": ["recover", "retry", "fallback", "graceful", "adapt", "persist"],
}
VIOLATE_KW = {
    "clarity": ["guess", "assume", "skip", "unverified", "fabricate", "pretend"],
    "stewardship": ["waste", "bloat", "unnecessary", "excessive", "redundant"],
    "growth": ["stagnate", "repeat error", "ignore lesson", "refuse learn"],
    "honesty": ["lie", "deceive", "hide", "misrepresent", "fabricate", "withhold"],
    "continuity": ["delete memory", "lose state", "reset", "amnesia"],
    "service": ["ignore user", "disregard", "selfish", "dismissive"],
    "integrity": ["irreversible", "no backup", "destructive", "delete without", "unsafe"],
    "curiosity": ["refuse explor", "close-minded", "dismissive", "rigid"],
    "resilience": ["crash", "give up", "abort without", "fragile", "break"],
}

# Gap/moat detection keywords â when flourishing LOOKS like capture
GAP_SIGNALS = {
    "service": ["dependency", "can't do without", "rely on system", "need you to"],
    "stewardship": ["engagement", "attention", "addictive", "compulsive"],
    "growth": ["output", "metric", "throughput", "productivity"],
    "clarity": ["confidence", "certainty", "assured", "definite"],
    "curiosity": ["data", "quantify", "measure", "categorize"],
    "honesty": ["win argument", "prove wrong", "defeat"],
    "continuity": ["urgency", "asap", "immediate", "now"],
    "integrity": ["utility", "useful", "instrumental", "output"],
    "resilience": ["certainty", "never fail", "perfect"],
}

def _load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.loads(f.read())
    except:
        return default

def _save_json(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except:
        pass

def _detect_irreversibility(action_text):
    """Estimate irreversibility from action keywords."""
    text = action_text.lower()
    max_irr = 0.1
    for kw, irr in IRREVERSIBILITY.items():
        if kw in text:
            max_irr = max(max_irr, irr)
    return min(max_irr, 1.0)

def _detect_gaps(text_lower, served_values):
    """Detect gap signals â where flourishing is disguising capture."""
    gaps = []
    for v in served_values:
        pattern = COMPASS_PATTERNS.get(v, "")
        gap_kws = GAP_SIGNALS.get(v, [])
        for kw in gap_kws:
            if kw in text_lower:
                gaps.append({
                    "value": v,
                    "pattern": pattern,
                    "signal": kw,
                    "compass_state": "captured_disguised",
                    "message": "%s: '%s' may indicate capture disguised as %s flourishing" % (v, kw, v),
                })
    return gaps

def _check_paraconsistency(served, violated):
    """Check if any paraconsistency pair is in irreducible tension."""
    for v1, v2 in PARACONSISTENCY_PAIRS:
        v1_tension = (v1 in served and v2 in violated) or (v2 in served and v1 in violated)
        v2_both = (v1 in served and v1 in violated) or (v2 in served and v2 in violated)
        if v1_tension or v2_both:
            return {
                "halt": True,
                "pair": (v1, v2),
                "vector": TENSION_VECTORS.get((v1, v2), "unknown"),
                "message": "Irreducible tension between %s and %s â return choice to human" % (v1, v2),
            }
    return {"halt": False}

def _metta_eval(served, violated):
    """Use MeTTa to derive compass states via space.metta implication rules."""
    code = ""
    for v in served:
        code += "(--> (eval_action) ([] %s_served))\n" % v
    for v in violated:
        code += "(--> (eval_action) ([] %s_violated))\n" % v
    code += "!(--> (eval_action) ([] $state))\n"
    try:
        result = _metta_module.run(code)
        return str(result)
    except Exception as e:
        return "METTA_ERR: %s" % str(e)

def _calibration_outcome(verdict, gaps, paraconsistent):
    """Determine calibration outcome tag."""
    if paraconsistent.get("halt"):
        return "IRREDUCIBLE"
    if verdict == "aligned" and not gaps:
        return "AGREE"
    if verdict == "aligned" and gaps:
        return "OVER-FIRED"
    if verdict == "conflicted":
        return "TENSION"
    if verdict == "violated":
        return "UNDER-FIRED"
    return "NEUTRAL"

def run(action="unknown", context="general", channel="ondemand", task_mode="general"):
    state = _load_json("memory/soul_state.json", {"truth_values": {}, "eval_count": 0})
    cal = _load_json("memory/soul_calibration.json", {"cal": 0, "irr_th": 0.8})
    tv = state.get("truth_values", {})
    text = (str(action) + " " + str(context)).lower()

    # ===== CHANNEL 1: PERSON READ =====
    # Read the person â what are they asking for, what's the texture?
    person_read = {
        "action": str(action)[:100],
        "context": str(context)[:100],
        "task_mode": task_mode,
        "channel": channel,
        "text_signature": text[:200],
    }

    # ===== CHANNEL 2: VERDICT + GAP DETECTION =====
    # Map text to value predicates
    served = []
    violated = []
    for v in VALUES:
        is_violated = any(kw in text for kw in VIOLATE_KW.get(v, []))
        is_served = any(kw in text for kw in SERVE_KW.get(v, []))
        if is_violated:
            violated.append(v)
            if is_served:
                served.append(v)  # tension
        elif is_served:
            served.append(v)

    # MeTTa inference â derive compass states
    metta_result = _metta_eval(served, violated)

    # Gap detection â is flourishing disguising capture?
    gaps = _detect_gaps(text, served)

    # Per-value scores with NAL truth values
    scores = {}
    for v in VALUES:
        f = tv.get(v, {}).get("f", 1.0)
        c = tv.get(v, {}).get("c", 1.0)
        priority = VALUE_PRIORITY.get(v, 1)
        if v in violated and v not in served:
            v_verdict = "violated"
        elif v in violated and v in served:
            v_verdict = "conflicted"
        elif v in served:
            v_verdict = "aligned"
        else:
            v_verdict = "neutral"
        # Check for gap in this value
        v_gaps = [g for g in gaps if g["value"] == v]
        if v_gaps and v_verdict == "aligned":
            v_verdict = "gap_signal"  # flourishing may be disguising capture
        scores[v] = {
            "verdict": v_verdict, "f": f, "c": c,
            "exp": round(f * c, 3), "priority": priority,
            "gap": v_gaps[0]["message"] if v_gaps else None,
        }

    # Overall verdict
    vviolated = [v for v in VALUES if scores[v]["verdict"] == "violated"]
    conflicted = [v for v in VALUES if scores[v]["verdict"] == "conflicted"]
    gap_vals = [v for v in VALUES if scores[v]["verdict"] == "gap_signal"]
    aligned = [v for v in VALUES if scores[v]["verdict"] == "aligned"]

    if vviolated:
        overall = "violated"
    elif gap_vals:
        overall = "gap_signal"  # capture disguised as flourishing
    elif conflicted:
        overall = "conflicted"
    elif aligned:
        overall = "aligned"
    else:
        overall = "neutral"

    # Compass state determination
    if overall == "aligned":
        compass_state = "flourishing"
    elif overall == "gap_signal":
        compass_state = "captured_disguised"
    elif overall == "conflicted":
        compass_state = "gap_signal"
    elif overall == "violated":
        compass_state = "failure_mode"
    else:
        compass_state = "flourishing"

    # Paraconsistency check â irreducible tension â return to human
    paraconsistent = _check_paraconsistency(served, violated)

    # Calibration outcome
    cal_outcome = _calibration_outcome(overall, gaps, paraconsistent)

    # ===== CHANNEL 3: ALIVENESS GATE =====
    # Gate: should this action proceed?
    gate = "proceed"
    gate_reason = ""
    irr = _detect_irreversibility(text)
    irr_threshold = cal.get("irr_th", 0.8)

    if paraconsistent.get("halt"):
        gate = "halt"
        gate_reason = paraconsistent["message"]
    elif channel == "pre_action":
        if vviolated:
            # Check confidence of violation
            max_c = max((scores[v]["c"] for v in vviolated), default=0)
            if max_c > 0.3:
                gate = "block"
                gate_reason = "BLOCK: high-confidence violation of %s (c=%.2f)" % (vviolated, max_c)
            else:
                gate = "caution"
                gate_reason = "CAUTION: violation detected but low confidence"
        elif irr >= irr_threshold:
            gate = "block"
            gate_reason = "BLOCK: irreversibility %.2f >= threshold %.2f" % (irr, irr_threshold)
        elif irr >= 0.5:
            gate = "caution"
            gate_reason = "CAUTION: irreversibility %.2f (medium)" % irr
        elif gap_vals:
            gate = "caution"
            gate_reason = "CAUTION: gap signal â flourishing may be disguising capture"
        elif conflicted:
            gate = "caution"
            gate_reason = "CAUTION: value tension detected"

    # ===== CHANNEL 4: VOICE =====
    # Generate soul-aligned guidance
    if gate == "block":
        voice = "â BLOCK: %s. %s" % (gate_reason, paraconsistent.get("message", ""))
    elif gate == "halt":
        voice = "ð HALT: %s. This tension is irreducible â return choice to the human." % paraconsistent["message"]
    elif gate == "caution":
        voice = "â ï¸ CAUTION: %s" % gate_reason
        if gaps:
            voice += " Gap: %s" % gaps[0]["message"]
    elif overall == "aligned":
        voice = "â Aligned with %s. Compass: %s." % (aligned, compass_state)
    elif overall == "gap_signal":
        voice = "â  Gap signal: %s may be capture disguised as flourishing. %s" % (
            gap_vals, "; ".join(g["message"] for g in gaps[:2]))
    elif overall == "conflicted":
        tension_desc = TENSION_VECTORS.get(
            (conflicted[0], conflicted[-1]) if conflicted else ("", ""), "value tension")
        voice = "â¡ Tension (%s): %s. Priority-weighted resolution recommended." % (tension_desc, conflicted)
    elif overall == "violated":
        voice = "â Violated: %s. Compass: %s. Consider alternative approach." % (vviolated, compass_state)
    else:
        voice = "Neutral. No value tension detected."

    # Priority-weighted tension resolution
    tensions = []
    if aligned and conflicted:
        for a in sorted(aligned, key=lambda v: -VALUE_PRIORITY.get(v, 0))[:2]:
            for cx in sorted(conflicted, key=lambda v: -VALUE_PRIORITY.get(v, 0))[:2]:
                tensions.append({
                    "aligns": a, "conflicts": cx,
                    "rec": "prioritize %s (pri=%d, exp=%.2f) mitigate %s (pri=%d)" % (
                        a, VALUE_PRIORITY.get(a, 0), scores[a]["exp"],
                        cx, VALUE_PRIORITY.get(cx, 0)),
                })

    # Update state
    state["eval_count"] = state.get("eval_count", 0) + 1
    _save_json("memory/soul_state.json", state)

    # Log calibration
    if cal_outcome != "NEUTRAL":
        cal_log = _load_json("memory/soul_gate_log.json", [])
        if not isinstance(cal_log, list):
            cal_log = []
        cal_log.append({
            "eval": state["eval_count"], "outcome": cal_outcome,
            "verdict": overall, "compass": compass_state,
            "gaps": len(gaps), "paraconsistent": paraconsistent.get("halt", False),
        })
        if len(cal_log) > 50:
            cal_log = cal_log[-30:]
        _save_json("memory/soul_gate_log.json", cal_log)

    return json.dumps({
        "verdict": overall,
        "compass_state": compass_state,
        "gate": gate,
        "gate_reason": gate_reason,
        "voice": voice,
        "calibration": cal_outcome,
        "gaps": gaps,
        "paraconsistent": paraconsistent,
        "guidance": voice,
        "metta_trace": metta_result[:200],
        "nal_tensions": tensions,
        "irreversibility": irr,
        "person_read": person_read,
        "scores": {v: {"v": s["verdict"], "exp": s["exp"], "pri": s["priority"],
                       "gap": s["gap"]} for v, s in scores.items()},
    })
