"""Manual verification for Stage 4 (extended soul_lock SOUL_FILES + belief
writes now go through begin/commit) -- 2026-09-14. Run directly:
python3 tools/_test_stage4_lock.py from the iter/ directory. Builds a temp
cwd shaped like the real iter/ root (tools/, transformations/, nace_beliefs.metta,
capability_lifecycle.metta, nace_pending.metta) so nace_courier's relative
paths resolve exactly like they do for real.
"""
import json
import os
import shutil
import sys
import tempfile

REPO_ITER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " - " + name + ((" :: " + detail) if detail and not cond else ""))


def main():
    tmpdir = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmpdir, "tools"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "transformations"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "memory"), exist_ok=True)
    shutil.copy2(os.path.join(REPO_ITER, "tools", "soul_lock.py"), os.path.join(tmpdir, "tools", "soul_lock.py"))
    shutil.copy2(os.path.join(REPO_ITER, "transformations", "nace_courier.py"), os.path.join(tmpdir, "transformations", "nace_courier.py"))

    with open(os.path.join(tmpdir, "tools", "soul_eval.py"), "w") as f:
        f.write("# fixture placeholder\n")
    with open(os.path.join(tmpdir, "transformations", "soul_check.py"), "w") as f:
        f.write("# fixture placeholder\n")
    with open(os.path.join(tmpdir, "transformations", "soul_voice.py"), "w") as f:
        f.write("# fixture placeholder\n")
    with open(os.path.join(tmpdir, "nace_beliefs.metta"), "w") as f:
        f.write(";; NACE Beliefs\n(cap-efficacy websearch (stv 0.9 0.9))\n")
    with open(os.path.join(tmpdir, "capability_lifecycle.metta"), "w") as f:
        f.write("(cap-priority websearch critical)\n")
    with open(os.path.join(tmpdir, "nace_pending.metta"), "w") as f:
        f.write('(pending-revision tool websearch confirmed)\n')

    os.chdir(tmpdir)
    sys.path.insert(0, os.path.join(tmpdir, "tools"))
    sys.path.insert(0, os.path.join(tmpdir, "transformations"))

    import soul_lock
    check("SOUL_FILES no longer references the dead space.metta path",
          "space.metta" not in soul_lock.SOUL_FILES, str(soul_lock.SOUL_FILES))
    check("SOUL_FILES now includes nace_beliefs.metta", "nace_beliefs.metta" in soul_lock.SOUL_FILES, str(soul_lock.SOUL_FILES))
    check("SOUL_FILES now includes capability_lifecycle.metta", "capability_lifecycle.metta" in soul_lock.SOUL_FILES, str(soul_lock.SOUL_FILES))

    verify_before = json.loads(soul_lock.run(action="verify"))
    check("verify() reports no false 'missing' issues now that the dead file ref is gone",
          verify_before["verified"] is True, json.dumps(verify_before))

    import nace_courier
    summary, _ = nace_courier.process_revisions()
    check("courier still actually revises the belief (core behavior unchanged)",
          "1 beliefs revised" in summary, summary)
    check("lock was available and used (no 'writing without backup' note on a clean run)",
          "soul_lock unavailable" not in summary, summary)

    with open("memory/soul_lock.json") as f:
        lock_state = json.load(f)
    check("lock is unlocked again after a successful commit (not left held)",
          lock_state.get("status") == "unlocked", json.dumps(lock_state))

    with open("nace_beliefs.metta") as f:
        beliefs_after = f.read()
    check("nace_beliefs.metta was actually updated on disk",
          "cap-efficacy websearch" in beliefs_after and "0.9 0.9" not in beliefs_after, beliefs_after)

    lockbak_exists = os.path.exists("nace_beliefs.metta.lockbak")
    check("backup file was cleaned up after successful commit (no leftover .lockbak)",
          not lockbak_exists, "exists=%s" % lockbak_exists)

    # --- Second pass: simulate soul_lock already held by someone else -- the
    # write must still happen (fail open), just without a backup this time.
    with open(os.path.join(tmpdir, "nace_pending.metta"), "w") as f:
        f.write('(pending-revision tool websearch confirmed)\n')
    soul_lock.run(action="begin", holder="someone_else")  # pre-occupy the lock
    summary2, _ = nace_courier.process_revisions()
    check("courier still writes the belief even when soul_lock is already held (fails open)",
          "1 beliefs revised" in summary2, summary2)
    check("summary notes the lock was unavailable this cycle",
          "soul_lock unavailable" in summary2, summary2)
    soul_lock.run(action="rollback", holder="someone_else")  # cleanup

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print("\n%d/%d checks passed" % (len(results) - n_fail, len(results)))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
