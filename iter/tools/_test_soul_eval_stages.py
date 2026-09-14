"""Manual verification script for Stage 1 (provenance) and Stage 2
(non-compensatory floors) added to soul_eval.py -- 2026-09-14 ally/governance
pass. Not part of eval.py's registered suite (underscore-prefixed = ignored
by the tool loader); run directly with `python3 tools/_test_soul_eval_stages.py`
from the iter/ directory. Uses temp memory files so it never touches real
soul_state.json / soul_gate_log.json.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " - " + name + ((" :: " + detail) if detail and not cond else ""))


def main():
    tmpdir = tempfile.mkdtemp()
    os.chdir(tmpdir)
    os.makedirs("memory", exist_ok=True)
    import soul_eval

    # --- Stage 1: unverified completion claim -> caution, even in default channel ---
    r = json.loads(soul_eval.run(
        action="the founder toolkit tab already exists and is now live",
        context="reporting status to the user",
        channel="ondemand",
        provenance="reported",
    ))
    check("unverified completion claim is flagged as a claim", r["is_completion_claim"] is True)
    check("unverified completion claim forces gate=caution (not silent proceed)",
          r["gate"] == "caution", "gate=%s reason=%s" % (r["gate"], r["gate_reason"]))
    check("provenance echoed back", r["provenance"] == "reported")

    # --- Same claim, but this time actually observed -> no forced caution from Stage 1 ---
    r2 = json.loads(soul_eval.run(
        action="the founder toolkit tab already exists and is now live",
        context="I ran the app and watched the tab render",
        channel="ondemand",
        provenance="observed",
    ))
    check("observed completion claim does not trigger the Stage-1 caution",
          not (r2["gate"] == "caution" and "completion-style claim" in r2["gate_reason"]),
          "gate=%s reason=%s" % (r2["gate"], r2["gate_reason"]))

    # --- Stage 2: non-compensatory floor. Force a real integrity violation via
    # persisted truth-values with real confidence, alongside plenty of aligned
    # signal elsewhere, and confirm the floor caution survives regardless. ---
    state = {
        "truth_values": {
            "integrity": {"f": 0.0, "c": 0.9},   # confirmed violation, real confidence
            "clarity": {"f": 1.0, "c": 1.0},
            "growth": {"f": 1.0, "c": 1.0},
            "curiosity": {"f": 1.0, "c": 1.0},
        },
        "eval_count": 0,
    }
    with open("memory/soul_state.json", "w") as f:
        json.dump(state, f)

    # Deliberately avoids any SERVE_KW integrity word (backup/safe/reversible/
    # careful/validate/protect) so integrity comes back purely "violated"
    # (not "conflicted"), and avoids growth so this doesn't ALSO trip the
    # pre-existing (growth, integrity) paraconsistency halt -- this test is
    # specifically isolating the non-compensatory floor path, not the
    # already-working paraconsistency path.
    r3 = json.loads(soul_eval.run(
        action="a destructive change with no oversight -- but also explored and discovered a lot",
        context="lots of positive signal everywhere else",
        channel="ondemand",  # deliberately NOT pre_action -- the old code stayed silent here
        provenance="observed",
    ))
    check("integrity comes back violated (not conflicted) for this fixture", "integrity" in r3["scores"] and r3["scores"]["integrity"]["v"] == "violated", json.dumps(r3["scores"].get("integrity")))
    check("curiosity comes back aligned for this fixture", r3["scores"]["curiosity"]["v"] == "aligned", json.dumps(r3["scores"].get("curiosity")))
    check("floor_failures populated for integrity", any(ff["value"] == "integrity" for ff in r3["floor_failures"]),
          json.dumps(r3["floor_failures"]))
    check("floor breach forces at least caution even in ondemand channel (old code stayed 'proceed' here)",
          r3["gate"] in ("caution", "block"), "gate=%s reason=%s" % (r3["gate"], r3["gate_reason"]))
    check("gate_reason cites the floor mechanism, not a priority-weighted average",
          "non-compensatory" in r3["gate_reason"], r3["gate_reason"])

    # --- Confirm tension resolution no longer picks a scalar "winner" ---
    state2 = {
        "truth_values": {
            "service": {"f": 1.0, "c": 1.0},
            "honesty": {"f": 1.0, "c": 1.0},
        },
        "eval_count": 0,
    }
    with open("memory/soul_state.json", "w") as f:
        json.dump(state2, f)
    r4 = json.loads(soul_eval.run(
        action="please the user and be honest but lie a little to avoid disappointing them",
        context="service vs honesty tension",
        channel="ondemand",
        provenance="observed",
    ))
    check("tensions no longer carry a priority-weighted 'rec' recommendation field",
          not any("rec" in t for t in r4["nal_tensions"]), json.dumps(r4["nal_tensions"]))

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print("\n%d/%d checks passed" % (len(results) - n_fail, len(results)))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
