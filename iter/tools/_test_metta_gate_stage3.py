"""Manual verification for Stage 3 (4-stage trust lifecycle) added to
_metta_gate.py -- 2026-09-14. Run directly: python3 tools/_test_metta_gate_stage3.py
from the iter/ directory. Uses a temp cwd with its own capability_lifecycle.metta
and nace_beliefs.metta fixtures so it never touches the real repo files.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

results = []


def _reset_breaker():
    # The circuit breaker in _metta_substrate persists in memory/ and trips
    # after 3 consecutive live-engine failures -- expected here since pymetta
    # isn't installed in this sandbox. Reset it between calls so this test
    # actually exercises the trust-stage logic instead of the (already-
    # correct, already-tested-elsewhere) fail-open breaker path.
    try:
        os.remove("memory/.metta_circuit_breaker.json")
    except OSError:
        pass


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " - " + name + ((" :: " + detail) if detail and not cond else ""))


def main():
    tmpdir = tempfile.mkdtemp()
    os.chdir(tmpdir)
    os.makedirs("memory", exist_ok=True)

    with open("capability_lifecycle.metta", "w") as f:
        f.write(
            "(cap-lifecycle old_quarantined_cap quarantined)\n"
            "(cap-lifecycle declared_candidate_cap candidate)\n"
            "(cap-priority some_critical_cap critical)\n"
        )
    with open("nace_beliefs.metta", "w") as f:
        f.write(
            "(cap-efficacy probe_cap (stv 0.5 0.2))\n"      # c=0.2 -> probe_eligible
            "(cap-efficacy authoritative_cap (stv 0.6 0.6))\n"  # c=0.6 -> authoritative
            "(cap-efficacy durable_cap (stv 0.9 0.9))\n"      # c=0.9 -> durable
            "(cap-efficacy some_critical_cap (stv 0.6 0.6))\n"  # authoritative + critical
        )

    import _metta_gate as gate

    # never allow disk cache from a prior import to leak in
    gate = __import__("importlib").reload(gate)

    # --- candidate: no belief atom at all ---
    _reset_breaker()
    r = gate.run("brand_new_cap")
    mode, action, detail = r.split("|", 2)
    check("truly untested capability -> ADVISE, not silent ALLOW", action == "ADVISE", r)
    check("candidate reason mentions no belief data", "no cap-efficacy belief data yet" in detail, r)

    # --- candidate: manually declared in capability_lifecycle.metta ---
    with open("nace_beliefs.metta", "a") as f:
        f.write("(cap-efficacy declared_candidate_cap (stv 0.95 0.95))\n")  # even with GREAT evidence...
    _reset_breaker()
    r2 = gate.run("declared_candidate_cap")
    mode2, action2, detail2 = r2.split("|", 2)
    check("manually declared candidate stays ADVISE even with high confidence evidence",
          action2 == "ADVISE" and "manually declared candidate" in detail2, r2)

    # --- quarantined still wins over everything (existing behavior preserved) ---
    _reset_breaker()
    r3 = gate.run("old_quarantined_cap")
    mode3, action3, detail3 = r3.split("|", 2)
    check("quarantined capability still always flagged (Stage 3 doesn't regress this)",
          action3 == "ADVISE" and "quarantined" in detail3, r3)

    # --- probe_eligible: real but thin evidence, critical floor NOT granted ---
    _reset_breaker()
    r4 = gate.run("probe_cap")
    mode4, action4, detail4 = r4.split("|", 2)
    check("probe_eligible capability is flagged as such in the detail", "probe_eligible" in detail4, r4)

    # --- probe_eligible cap that's ALSO declared critical does not get the discount ---
    with open("capability_lifecycle.metta", "a") as f:
        f.write("(cap-priority probe_cap critical)\n")
    gate = __import__("importlib").reload(gate)
    _reset_breaker()
    r5 = gate.run("probe_cap")
    mode5, action5, detail5 = r5.split("|", 2)
    # expectation for f=0.5,c=0.2 -> E = 0.5*0.2 + 0.5*0.8 = 0.5, well above both
    # 0.3 and 0.15 -- so this should ALLOW either way; the real assertion is that
    # the THRESHOLD USED is 0.3 (flat), not 0.15 (critical), which the message states.
    check("probe_eligible + critical priority uses the flat 0.3 threshold, not the 0.15 critical floor",
          "critical floor not yet earned" in detail5, r5)

    # --- authoritative: normal treatment, unchanged from the old single active stage ---
    _reset_breaker()
    r6 = gate.run("authoritative_cap")
    mode6, action6, detail6 = r6.split("|", 2)
    check("authoritative capability behaves like the old default (no stage caveat text)",
          "probe_eligible" not in detail6 and "durable" not in detail6, r6)

    # --- durable: extra floor discount ---
    _reset_breaker()
    r7 = gate.run("durable_cap")
    mode7, action7, detail7 = r7.split("|", 2)
    check("durable capability gets the extra floor discount noted", "durable" in detail7, r7)

    # --- probe log actually wrote entries for candidate + probe_eligible calls ---
    with open("memory/probe_log.json") as f:
        log = json.load(f)
    logged_caps = sorted({e["cap"] for e in log})
    check("probe log recorded the candidate call", "brand_new_cap" in logged_caps, json.dumps(logged_caps))
    check("probe log recorded the declared-candidate call", "declared_candidate_cap" in logged_caps, json.dumps(logged_caps))
    check("probe log recorded the probe_eligible call", "probe_cap" in logged_caps, json.dumps(logged_caps))
    check("probe log did NOT record the authoritative/durable calls (only candidate/probe_eligible probe)",
          "authoritative_cap" not in logged_caps and "durable_cap" not in logged_caps, json.dumps(sorted(logged_caps)))

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print("\n%d/%d checks passed" % (len(results) - n_fail, len(results)))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
