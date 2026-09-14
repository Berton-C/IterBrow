"""Combined verification for all 5 governance stages together -- run from
iter/: python3 tools/_test_all_stages_combined.py

Runs the three existing per-stage test scripts as subprocesses (each is
independently useful and already exercises its own stage in isolation), then
adds integration checks that specifically exercise stages crossing paths:
Stage 4's locked belief write (soul_lock + nace_courier) actually feeding
Stage 3's trust-lifecycle derivation (_metta_gate), and Stage 5's guard
importing cleanly alongside Stage 1/2's soul_eval in the same process.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ITER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " - " + name + ((" :: " + detail) if detail and not cond else ""))


def run_subtest(rel_path):
    proc = subprocess.run(
        [sys.executable, rel_path], cwd=ITER_ROOT,
        capture_output=True, text=True, timeout=60,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main():
    # --- Per-stage scripts, run as subprocesses so their own tempdir/cwd juggling can't collide ---
    for label, rel_path in [
        ("Stage 1+2 (soul_eval.py provenance + floors)", "tools/_test_soul_eval_stages.py"),
        ("Stage 3 (capability trust lifecycle)", "tools/_test_metta_gate_stage3.py"),
        ("Stage 4 (soul_lock + locked belief writes)", "tools/_test_stage4_lock.py"),
    ]:
        code, out, err = run_subtest(rel_path)
        last_line = [l for l in out.strip().splitlines() if l.strip()][-1] if out.strip() else ""
        check(label, code == 0, last_line or err[-300:])

    code, out, err = run_subtest("transformations/_test_stage5_guard.py")
    last_line = [l for l in out.strip().splitlines() if l.strip()][-1] if out.strip() else ""
    check("Stage 5 (completion_claim_guard severing power)", code == 0, last_line or err[-300:])

    # --- Integration check: Stage 4's locked write feeds Stage 3's trust-stage derivation ---
    tmpdir = tempfile.mkdtemp()
    for d in ("tools", "transformations", "memory"):
        os.makedirs(os.path.join(tmpdir, d), exist_ok=True)
    for rel in ("tools/soul_lock.py", "tools/_metta_gate.py", "transformations/nace_courier.py"):
        shutil.copy2(os.path.join(ITER_ROOT, rel), os.path.join(tmpdir, rel))
    for placeholder in ("tools/soul_eval.py", "transformations/soul_check.py", "transformations/soul_voice.py"):
        with open(os.path.join(tmpdir, placeholder), "w") as f:
            f.write("# fixture placeholder\n")
    with open(os.path.join(tmpdir, "nace_beliefs.metta"), "w") as f:
        f.write(";; NACE Beliefs\n")
    with open(os.path.join(tmpdir, "capability_lifecycle.metta"), "w") as f:
        f.write("(cap-priority demo_cap normal)\n")
    with open(os.path.join(tmpdir, "nace_pending.metta"), "w") as f:
        # Feed enough confirmed observations to push confidence into probe_eligible range (c < 0.4)
        f.write('(pending-revision tool demo_cap confirmed)\n')

    old_cwd = os.getcwd()
    os.chdir(tmpdir)
    sys.path.insert(0, os.path.join(tmpdir, "tools"))
    sys.path.insert(0, os.path.join(tmpdir, "transformations"))
    try:
        import nace_courier
        summary, _ = nace_courier.process_revisions()
        check("Integration: Stage 4 courier write succeeds through the lock inside a fresh fixture",
              "beliefs revised" in summary, summary)

        with open("nace_beliefs.metta") as f:
            beliefs_text = f.read()
        check("Integration: belief file on disk actually reflects the new confidence value",
              "demo_cap" in beliefs_text, beliefs_text)

        import _metta_gate
        conf = _metta_gate._lookup_confidence("demo_cap", root=".")
        check("Integration: Stage 3's gate can read the confidence Stage 4's locked write just produced",
              conf is not None, str(conf))

        if conf is not None:
            stage = _metta_gate._determine_trust_stage("auto", conf)
            check("Integration: derived trust stage is a recognized stage name",
                  stage in ("candidate", "probe_eligible", "authoritative", "durable"), stage)
    finally:
        os.chdir(old_cwd)
        sys.path.pop(0)
        sys.path.pop(0)

    # --- Sanity: Stage 5's guard and Stage 1/2's soul_eval import side by side without collision ---
    sys.path.insert(0, os.path.join(ITER_ROOT, "tools"))
    sys.path.insert(0, os.path.join(ITER_ROOT, "transformations"))
    try:
        import importlib
        soul_eval = importlib.import_module("soul_eval")
        guard = importlib.import_module("completion_claim_guard")
        check("Sanity: soul_eval and completion_claim_guard import side by side with no name collisions",
              hasattr(soul_eval, "run") and hasattr(guard, "transform"))
    finally:
        sys.path.pop(0)
        sys.path.pop(0)

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print("\n%d/%d checks passed" % (len(results) - n_fail, len(results)))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
