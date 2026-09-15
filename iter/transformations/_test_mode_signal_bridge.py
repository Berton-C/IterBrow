"""Manual verification for mode_signal_bridge.py (the add/subtract/loosen
first slice, 2026-09-15) plus nace_courier.py's new "mode" prefix and
OPENING surfacing line. Run directly:
    python3 transformations/_test_mode_signal_bridge.py
from the iter/ directory. Mirrors _test_flourishing_bridges.py's
fixture-repo convention (tmpdir chdir + fresh module import per case).
"""
import importlib.util
import os
import shutil
import sys
import tempfile

REPO_ITER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSFORMS_DIR = os.path.join(REPO_ITER, "transformations")
TOOLS_DIR = os.path.join(REPO_ITER, "tools")

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " - " + name + ((" :: " + detail) if detail else ""))


def pending_lines(tmpdir):
    path = os.path.join(tmpdir, "nace_pending.metta")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [l.strip() for l in f if l.strip().startswith("(pending-revision")]


def beliefs_text(tmpdir):
    path = os.path.join(tmpdir, "nace_beliefs.metta")
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        return f.read()


def setup_fixture_repo(tmpdir):
    os.makedirs(os.path.join(tmpdir, "tools"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "transformations"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "memory"), exist_ok=True)
    shutil.copy(os.path.join(TOOLS_DIR, "_provenance.py"), os.path.join(tmpdir, "tools", "_provenance.py"))
    with open(os.path.join(tmpdir, "nace_pending.metta"), "w") as f:
        f.write(";; NACE Pending\n")
    with open(os.path.join(tmpdir, "nace_beliefs.metta"), "w") as f:
        f.write(";; NACE Beliefs\n")
    with open(os.path.join(tmpdir, "iter.py"), "w") as f:
        f.write("from pathlib import Path\n")


def load_module(name, path, tmpdir, extra_sys_path=None):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    if extra_sys_path:
        for p in extra_sys_path:
            if p not in sys.path:
                sys.path.insert(0, p)
    if name in sys.modules:
        del sys.modules[name]
    spec.loader.exec_module(mod)
    return mod


def make_msg(role, content):
    return {"role": role, "content": content}


def test_bridge_records_only_on_transition():
    tmpdir = tempfile.mkdtemp()
    old_cwd = os.getcwd()
    try:
        setup_fixture_repo(tmpdir)
        os.chdir(tmpdir)
        bridge = load_module(
            "mode_signal_bridge",
            os.path.join(TRANSFORMS_DIR, "mode_signal_bridge.py"),
            tmpdir,
            extra_sys_path=[os.path.join(tmpdir, "tools")],
        )

        open_msg = [make_msg("system", "sys"), make_msg("user", "what do you think might be going on here, I'm curious?")]
        closed_msg_1 = [make_msg("system", "sys"), make_msg("user", "This is obviously always going to fail, we simply have to accept it, no doubt.")]
        closed_msg_2 = [make_msg("system", "sys"), make_msg("user", "It's clearly the only way -- we must never revisit this, it's simply certain.")]

        bridge.transform(open_msg, [])
        check("cycle 1 (open language) records nothing", pending_lines(tmpdir) == [])

        bridge.transform(closed_msg_1, [])
        check("cycle 2 (closed, but window not full) records nothing yet", pending_lines(tmpdir) == [])

        bridge.transform(closed_msg_2, [])
        lines = pending_lines(tmpdir)
        check("cycle 3 (closed x2 -> repeated) records exactly one confirmed", lines == ["(pending-revision mode mode_loosen confirmed)"], str(lines))

        # Repeat once more: window is still all-closed, but this is not a
        # NEW transition, so nothing new should be recorded (no double count).
        bridge.transform(closed_msg_2, [])
        check("cycle 4 (still repeated, no new transition) records nothing new", pending_lines(tmpdir) == lines, str(pending_lines(tmpdir)))

        # Now break it with open language -- should record disconfirmed.
        bridge.transform(open_msg, [])
        lines = pending_lines(tmpdir)
        check(
            "cycle 5 (loop broken) records disconfirmed",
            lines == ["(pending-revision mode mode_loosen confirmed)", "(pending-revision mode mode_loosen disconfirmed)"],
            str(lines),
        )
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_courier_surfaces_opening_after_enough_evidence():
    tmpdir = tempfile.mkdtemp()
    old_cwd = os.getcwd()
    try:
        setup_fixture_repo(tmpdir)
        os.chdir(tmpdir)
        courier = load_module(
            "nace_courier",
            os.path.join(TRANSFORMS_DIR, "nace_courier.py"),
            tmpdir,
        )

        # Feed repeated independent "confirmed" mode_loosen cycles the way
        # the bridge would across separate closed-then-broken stretches of a
        # long session -- checking the SAME Truth_Revision math and
        # surfacing threshold as the 9 compass patterns, just a new prefix.
        # nal_revise's harmonic confidence growth (exp = c*(f-0.5)+0.5,
        # each further (f=1.0,c=0.1) observation adding diminishing weight)
        # means exp only strictly clears the 0.7 bar after the 7th
        # confirmation -- checked at 6 (not yet) and 7 (now) below.
        summary = ""
        for i in range(6):
            with open(os.path.join(tmpdir, "nace_pending.metta"), "a") as f:
                f.write("(pending-revision mode mode_loosen confirmed)\n")
            summary, _ = courier.process_revisions()
        check("after 6 confirmed cycles: no OPENING yet (confidence too low)", "OPENING" not in summary, summary)

        with open(os.path.join(tmpdir, "nace_pending.metta"), "a") as f:
            f.write("(pending-revision mode mode_loosen confirmed)\n")
        summary3, _ = courier.process_revisions()
        check("7th confirmed cycle: OPENING now surfaces", "OPENING: mode:mode_loosen" in summary3, summary3)

        text = beliefs_text(tmpdir)
        check("belief written under the new mode-signal prefix", "(mode-signal mode_loosen (stv" in text, text)

        # transform() should append the OPENING note onto the system message.
        with open(os.path.join(tmpdir, "nace_pending.metta"), "a") as f:
            f.write("(pending-revision mode mode_loosen confirmed)\n")
        messages = [{"role": "system", "content": "base prompt"}]
        messages, _ = courier.transform(messages, [])
        check("transform() appends OPENING onto the system message", "OPENING: mode:mode_loosen" in messages[0]["content"], messages[0]["content"])

        # And a real, unrelated LOW EFFICACY pattern belief should still
        # behave exactly as before -- this new prefix must not perturb it.
        # (Mirrors the same harmonic threshold: 7 violated cycles needed.)
        summary4 = ""
        for i in range(7):
            with open(os.path.join(tmpdir, "nace_pending.metta"), "a") as f:
                f.write("(pending-revision pattern some_pattern violated)\n")
            summary4, _ = courier.process_revisions()
        check("unrelated pattern-efficacy LOW EFFICACY path still fires normally", "LOW EFFICACY: pattern:some_pattern" in summary4, summary4)
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    test_bridge_records_only_on_transition()
    test_courier_surfaces_opening_after_enough_evidence()
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("\n%d/%d passed" % (passed, total))
    sys.exit(0 if passed == total else 1)
