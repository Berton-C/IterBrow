"""Manual verification for the flourishing-reinterpretation evidence
bridges added 2026-09-15: admit_uncertainty_bridge.py, time_coherence_
bridge.py, attention_stewardship_bridge.py, and staleness_check.py's new
maintain_memory hook. Run directly:
    python3 transformations/_test_flourishing_bridges.py
from the iter/ directory. Mirrors _test_provenance_guard.py's fixture-repo
convention (tmpdir chdir + fresh module import per case).
"""
import importlib.util
import json
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
    print(("PASS" if cond else "FAIL") + " - " + name + ((" :: " + detail) if detail and not cond else ""))


def pending_lines(tmpdir):
    path = os.path.join(tmpdir, "nace_pending.metta")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [l.strip() for l in f if l.strip().startswith("(pending-revision")]


def setup_fixture_repo(tmpdir):
    os.makedirs(os.path.join(tmpdir, "tools"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "transformations"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "memory"), exist_ok=True)
    shutil.copy(os.path.join(TOOLS_DIR, "_provenance.py"), os.path.join(tmpdir, "tools", "_provenance.py"))
    shutil.copy(os.path.join(TRANSFORMS_DIR, "completion_claim_guard.py"),
                os.path.join(tmpdir, "transformations", "completion_claim_guard.py"))
    with open(os.path.join(tmpdir, "nace_pending.metta"), "w") as f:
        f.write(";; NACE Pending\n")
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


def base_messages():
    return [{"role": "system", "content": "system prompt"}]


# ============================================================
# admit_uncertainty_bridge.py
# ============================================================
def test_admit_uncertainty_bridge():
    tmp = tempfile.mkdtemp()
    setup_fixture_repo(tmp)
    os.chdir(tmp)
    sys.path.insert(0, os.path.join(tmp, "transformations"))
    bridge = load_module("admit_uncertainty_bridge",
                          os.path.join(TRANSFORMS_DIR, "admit_uncertainty_bridge.py"), tmp,
                          extra_sys_path=[os.path.join(tmp, "tools")])
    bridge.STATE_PATH = os.path.join(tmp, "memory", ".admit_uncertainty_state.json")

    # No task_state.metta at all -> not verified -> violated on both patterns
    messages = base_messages() + [{"role": "assistant", "content": "The dashboard is now live and verified."}]
    new_messages, _ = bridge.transform(list(messages), [])
    lines = pending_lines(tmp)
    check("admit_uncertainty_bridge: unverified claim -> violated on admit_uncertainty",
          "(pending-revision pattern admit_uncertainty violated)" in lines, str(lines))
    check("admit_uncertainty_bridge: unverified claim -> violated on verify_before_claiming too",
          "(pending-revision pattern verify_before_claiming violated)" in lines, str(lines))
    check("admit_uncertainty_bridge: appends an advisory note, does not touch tools",
          "Admit Uncertainty" in new_messages[0]["content"], new_messages[0]["content"])

    # Idempotency: same fingerprint must not re-emit
    before = pending_lines(tmp)
    bridge.transform(list(messages), [])
    after = pending_lines(tmp)
    check("admit_uncertainty_bridge: idempotent on identical unresolved claim",
          before == after, "before=%s after=%s" % (before, after))

    # Now mark verifying -> a NEW distinct message should record confirmed
    with open(os.path.join(tmp, "task_state.metta"), "w") as f:
        f.write('(task-phase "dashboard" verifying "") ;; ts\n')
    messages2 = base_messages() + [{"role": "assistant", "content": "The dashboard build is now complete and verified for real."}]
    bridge.transform(list(messages2), [])
    lines2 = pending_lines(tmp)
    check("admit_uncertainty_bridge: verified phase -> confirmed",
          "(pending-revision pattern admit_uncertainty confirmed)" in lines2, str(lines2))


# ============================================================
# time_coherence_bridge.py
# ============================================================
def test_time_coherence_bridge():
    tmp = tempfile.mkdtemp()
    setup_fixture_repo(tmp)
    os.chdir(tmp)
    bridge = load_module("time_coherence_bridge",
                          os.path.join(TRANSFORMS_DIR, "time_coherence_bridge.py"), tmp,
                          extra_sys_path=[os.path.join(tmp, "tools")])
    bridge.LOCK_PATH = os.path.join(tmp, "memory", "soul_lock.json")
    bridge.STATE_PATH = os.path.join(tmp, "memory", ".time_coherence_state.json")

    import time
    stuck_lock = {"status": "locked", "holder": "nace_courier", "timestamp": int(time.time()) - 600, "backups": {}}
    with open(bridge.LOCK_PATH, "w") as f:
        json.dump(stuck_lock, f)

    messages = base_messages()
    new_messages, _ = bridge.transform(list(messages), [])
    lines = pending_lines(tmp)
    check("time_coherence_bridge: stale locked transaction -> violated",
          "(pending-revision pattern backup_before_change violated)" in lines, str(lines))

    # Re-running while still stuck must not double-record
    before = pending_lines(tmp)
    bridge.transform(list(messages), [])
    after = pending_lines(tmp)
    check("time_coherence_bridge: does not re-emit while still stuck",
          before == after, "before=%s after=%s" % (before, after))

    # Lock clears -> confirmed once
    with open(bridge.LOCK_PATH, "w") as f:
        json.dump({"status": "unlocked", "holder": None, "timestamp": None, "backups": {}}, f)
    bridge.transform(list(messages), [])
    lines2 = pending_lines(tmp)
    check("time_coherence_bridge: cleared lock after being stuck -> confirmed",
          "(pending-revision pattern backup_before_change confirmed)" in lines2, str(lines2))

    # A healthy never-stuck unlocked state must never emit
    tmp2 = tempfile.mkdtemp()
    setup_fixture_repo(tmp2)
    os.chdir(tmp2)
    bridge2 = load_module("time_coherence_bridge",
                           os.path.join(TRANSFORMS_DIR, "time_coherence_bridge.py"), tmp2,
                           extra_sys_path=[os.path.join(tmp2, "tools")])
    bridge2.LOCK_PATH = os.path.join(tmp2, "memory", "soul_lock.json")
    bridge2.STATE_PATH = os.path.join(tmp2, "memory", ".time_coherence_state.json")
    with open(bridge2.LOCK_PATH, "w") as f:
        json.dump({"status": "unlocked", "holder": None, "timestamp": None, "backups": {}}, f)
    bridge2.transform(base_messages(), [])
    check("time_coherence_bridge: healthy never-stuck unlocked state emits nothing",
          pending_lines(tmp2) == [], str(pending_lines(tmp2)))


# ============================================================
# attention_stewardship_bridge.py
# ============================================================
def test_attention_stewardship_bridge():
    tmp = tempfile.mkdtemp()
    setup_fixture_repo(tmp)
    os.chdir(tmp)
    bridge = load_module("attention_stewardship_bridge",
                          os.path.join(TRANSFORMS_DIR, "attention_stewardship_bridge.py"), tmp,
                          extra_sys_path=[os.path.join(tmp, "tools")])
    bridge.BUDGET_FILE = os.path.join(tmp, "transformations", ".runtime", "tool_budget.json")
    bridge.TRANSCRIPT_PATH = os.path.join(tmp, "transcript.txt")
    bridge.STATE_PATH = os.path.join(tmp, "memory", ".attention_stewardship_state.json")

    os.makedirs(os.path.dirname(bridge.BUDGET_FILE), exist_ok=True)
    with open(bridge.BUDGET_FILE, "w") as f:
        json.dump({"budget": 5, "signals": {}, "hidden": [], "mem_chars": 0}, f)

    # 20 calls then a send -- way over budget*1.5=7.5
    lines_out = ["[2026-09-15 00:00:0%d] [shell cmd]" % i for i in range(9)]
    lines_out.append("[2026-09-15 00:00:10] [send]")
    with open(bridge.TRANSCRIPT_PATH, "w") as f:
        f.write("\n".join(lines_out) + "\n")

    bridge.transform(base_messages(), [])
    lines = pending_lines(tmp)
    check("attention_stewardship_bridge: overspend past budget*1.5 -> violated",
          "(pending-revision pattern conserve_cycles violated)" in lines, str(lines))

    # Within budget cycle -> confirmed
    tmp2 = tempfile.mkdtemp()
    setup_fixture_repo(tmp2)
    os.chdir(tmp2)
    bridge2 = load_module("attention_stewardship_bridge",
                           os.path.join(TRANSFORMS_DIR, "attention_stewardship_bridge.py"), tmp2,
                           extra_sys_path=[os.path.join(tmp2, "tools")])
    bridge2.BUDGET_FILE = os.path.join(tmp2, "transformations", ".runtime", "tool_budget.json")
    bridge2.TRANSCRIPT_PATH = os.path.join(tmp2, "transcript.txt")
    bridge2.STATE_PATH = os.path.join(tmp2, "memory", ".attention_stewardship_state.json")
    os.makedirs(os.path.dirname(bridge2.BUDGET_FILE), exist_ok=True)
    with open(bridge2.BUDGET_FILE, "w") as f:
        json.dump({"budget": 10, "signals": {}, "hidden": [], "mem_chars": 0}, f)
    lines_out2 = ["[2026-09-15 00:00:0%d] [shell cmd]" % i for i in range(3)]
    lines_out2.append("[2026-09-15 00:00:10] [send]")
    with open(bridge2.TRANSCRIPT_PATH, "w") as f:
        f.write("\n".join(lines_out2) + "\n")
    bridge2.transform(base_messages(), [])
    lines2 = pending_lines(tmp2)
    check("attention_stewardship_bridge: within budget -> confirmed",
          "(pending-revision pattern conserve_cycles confirmed)" in lines2, str(lines2))

    # Mid-stream (no trailing send) must not judge at all
    tmp3 = tempfile.mkdtemp()
    setup_fixture_repo(tmp3)
    os.chdir(tmp3)
    bridge3 = load_module("attention_stewardship_bridge",
                           os.path.join(TRANSFORMS_DIR, "attention_stewardship_bridge.py"), tmp3,
                           extra_sys_path=[os.path.join(tmp3, "tools")])
    bridge3.BUDGET_FILE = os.path.join(tmp3, "transformations", ".runtime", "tool_budget.json")
    bridge3.TRANSCRIPT_PATH = os.path.join(tmp3, "transcript.txt")
    bridge3.STATE_PATH = os.path.join(tmp3, "memory", ".attention_stewardship_state.json")
    os.makedirs(os.path.dirname(bridge3.BUDGET_FILE), exist_ok=True)
    with open(bridge3.BUDGET_FILE, "w") as f:
        json.dump({"budget": 2, "signals": {}, "hidden": [], "mem_chars": 0}, f)
    with open(bridge3.TRANSCRIPT_PATH, "w") as f:
        f.write("[2026-09-15 00:00:01] [shell cmd]\n[2026-09-15 00:00:02] [shell cmd]\n")
    bridge3.transform(base_messages(), [])
    check("attention_stewardship_bridge: mid-cycle (no trailing send) never judged",
          pending_lines(tmp3) == [], str(pending_lines(tmp3)))


# ============================================================
# staleness_check.py's new maintain_memory hook
# ============================================================
def test_staleness_check_maintain_memory():
    tmp = tempfile.mkdtemp()
    setup_fixture_repo(tmp)
    os.chdir(tmp)
    check_mod = load_module("staleness_check",
                             os.path.join(TRANSFORMS_DIR, "staleness_check.py"), tmp,
                             extra_sys_path=[os.path.join(tmp, "tools")])
    check_mod.AGENTS_MD = os.path.join(tmp, "AGENTS.md")
    check_mod.DIRS = {"tools": os.path.join(tmp, "tools")}
    check_mod._PATTERN_STATE_PATH = os.path.join(tmp, "memory", ".staleness_pattern_state.json")

    with open(check_mod.AGENTS_MD, "w") as f:
        f.write("# AGENTS\nDocuments nothing relevant here.\n")
    with open(os.path.join(tmp, "tools", "undocumented_tool.py"), "w") as f:
        f.write("def run(): pass\n")

    # 2 stale cycles -> below threshold (3), should not record yet
    check_mod.transform(base_messages(), [])
    check_mod.transform(base_messages(), [])
    check("staleness_check: below streak threshold does not record yet",
          pending_lines(tmp) == [], str(pending_lines(tmp)))

    # 3rd consecutive stale cycle crosses threshold -> violated
    check_mod.transform(base_messages(), [])
    lines = pending_lines(tmp)
    check("staleness_check: 3rd consecutive stale cycle -> violated for maintain_memory",
          "(pending-revision pattern maintain_memory violated)" in lines, str(lines))

    # Fix AGENTS.md -> next clean cycle should record confirmed once
    with open(check_mod.AGENTS_MD, "a") as f:
        f.write("undocumented_tool.py\n")
    check_mod.transform(base_messages(), [])
    lines2 = pending_lines(tmp)
    check("staleness_check: drift resolved after being recorded -> confirmed",
          "(pending-revision pattern maintain_memory confirmed)" in lines2, str(lines2))


def main():
    orig_cwd = os.getcwd()
    try:
        test_admit_uncertainty_bridge()
        test_time_coherence_bridge()
        test_attention_stewardship_bridge()
        test_staleness_check_maintain_memory()
    finally:
        os.chdir(orig_cwd)

    print("\n%d/%d checks passed" % (sum(1 for _, ok, _ in results if ok), len(results)))
    if not all(ok for _, ok, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
