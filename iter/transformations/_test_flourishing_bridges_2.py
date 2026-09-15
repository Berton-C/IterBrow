"""Manual verification for the second batch of flourishing-reinterpretation
evidence bridges added 2026-09-15: creative_transcendence_bridge.py,
connection_depth_bridge.py, wonder_preservation_bridge.py. Run directly:
    python3 transformations/_test_flourishing_bridges_2.py
from the iter/ directory. Mirrors _test_flourishing_bridges.py's fixture
convention.
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
    shutil.copy(os.path.join(TRANSFORMS_DIR, "auto_improve.py"), os.path.join(tmpdir, "transformations", "auto_improve.py"))
    shutil.copy(os.path.join(TRANSFORMS_DIR, "dynamic_tool_budget.py"), os.path.join(tmpdir, "transformations", "dynamic_tool_budget.py"))
    with open(os.path.join(tmpdir, "nace_pending.metta"), "w") as f:
        f.write(";; NACE Pending\n")


def load_module(name, path, extra_sys_path=None):
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
# creative_transcendence_bridge.py
# ============================================================
def test_creative_transcendence_bridge():
    tmp = tempfile.mkdtemp()
    setup_fixture_repo(tmp)
    os.chdir(tmp)
    bridge = load_module("creative_transcendence_bridge",
                          os.path.join(TRANSFORMS_DIR, "creative_transcendence_bridge.py"),
                          extra_sys_path=[os.path.join(tmp, "tools"), os.path.join(tmp, "transformations")])
    bridge.RELIABILITY_FILE = os.path.join(tmp, "transformations", ".runtime", "tool_reliability.json")
    bridge.BUDGET_FILE = os.path.join(tmp, "transformations", ".runtime", "tool_budget.json")
    bridge.STATE_PATH = os.path.join(tmp, "memory", ".creative_transcendence_state.json")
    os.makedirs(os.path.join(tmp, "transformations", ".runtime"), exist_ok=True)

    # Tool has clear low-reliability evidence but budget.json doesn't hide it
    with open(bridge.RELIABILITY_FILE, "w") as f:
        json.dump({"flaky_tool": {"f": 0.2, "c": 0.8, "calls": 5, "successes": 1, "failures": 4}}, f)
    with open(bridge.BUDGET_FILE, "w") as f:
        json.dump({"budget": 10, "signals": {}, "hidden": [], "mem_chars": 0}, f)

    bridge.transform(base_messages(), [])
    lines = pending_lines(tmp)
    check("creative_transcendence_bridge: low-reliability tool not hidden -> violated",
          "(pending-revision pattern learn_from_experience violated)" in lines, str(lines))

    # Re-run with unchanged state must not double-record
    before = pending_lines(tmp)
    bridge.transform(base_messages(), [])
    after = pending_lines(tmp)
    check("creative_transcendence_bridge: no re-emit on unchanged state",
          before == after, "before=%s after=%s" % (before, after))

    # Now budget.json reflects the tool as hidden -> confirmed
    with open(bridge.BUDGET_FILE, "w") as f:
        json.dump({"budget": 10, "signals": {}, "hidden": ["flaky_tool (f=0.20,5 calls)"], "mem_chars": 0}, f)
    bridge.transform(base_messages(), [])
    lines2 = pending_lines(tmp)
    check("creative_transcendence_bridge: tool now hidden -> confirmed",
          "(pending-revision pattern learn_from_experience confirmed)" in lines2, str(lines2))

    # Reliable tool never triggers anything
    tmp2 = tempfile.mkdtemp()
    setup_fixture_repo(tmp2)
    os.chdir(tmp2)
    bridge2 = load_module("creative_transcendence_bridge",
                           os.path.join(TRANSFORMS_DIR, "creative_transcendence_bridge.py"),
                           extra_sys_path=[os.path.join(tmp2, "tools")])
    bridge2.RELIABILITY_FILE = os.path.join(tmp2, "transformations", ".runtime", "tool_reliability.json")
    bridge2.BUDGET_FILE = os.path.join(tmp2, "transformations", ".runtime", "tool_budget.json")
    bridge2.STATE_PATH = os.path.join(tmp2, "memory", ".creative_transcendence_state.json")
    os.makedirs(os.path.join(tmp2, "transformations", ".runtime"), exist_ok=True)
    with open(bridge2.RELIABILITY_FILE, "w") as f:
        json.dump({"good_tool": {"f": 0.95, "c": 0.9, "calls": 10, "successes": 9, "failures": 1}}, f)
    bridge2.transform(base_messages(), [])
    check("creative_transcendence_bridge: reliable tool emits nothing",
          pending_lines(tmp2) == [], str(pending_lines(tmp2)))


# ============================================================
# connection_depth_bridge.py
# ============================================================
def test_connection_depth_bridge():
    tmp = tempfile.mkdtemp()
    setup_fixture_repo(tmp)
    os.chdir(tmp)
    bridge = load_module("connection_depth_bridge",
                          os.path.join(TRANSFORMS_DIR, "connection_depth_bridge.py"),
                          extra_sys_path=[os.path.join(tmp, "tools"), os.path.join(tmp, "transformations")])
    bridge.TRANSCRIPT_PATH = os.path.join(tmp, "transcript.txt")
    bridge.STATE_PATH = os.path.join(tmp, "memory", ".connection_depth_state.json")

    # 6 calls since last send, one has a real traceback, still no send -> violated
    lines_out = [
        "[2026-09-15 00:00:00] [send]",
        "[2026-09-15 00:00:01] [shell cmd]",
        "[2026-09-15 00:00:02] [python code]  Traceback (most recent call last):",
        "[2026-09-15 00:00:03] [shell cmd]",
        "[2026-09-15 00:00:04] [shell cmd]",
        "[2026-09-15 00:00:05] [shell cmd]",
        "[2026-09-15 00:00:06] [shell cmd]",
    ]
    with open(bridge.TRANSCRIPT_PATH, "w") as f:
        f.write("\n".join(lines_out) + "\n")
    new_messages, _ = bridge.transform(base_messages(), [])
    lines = pending_lines(tmp)
    check("connection_depth_bridge: error worked around in silence past threshold -> violated",
          "(pending-revision pattern recover_gracefully violated)" in lines, str(lines))
    check("connection_depth_bridge: appends an advisory note",
          "Connection Depth" in new_messages[0]["content"], new_messages[0]["content"])

    # Error surfaced: same error then an immediate send -> confirmed
    tmp2 = tempfile.mkdtemp()
    setup_fixture_repo(tmp2)
    os.chdir(tmp2)
    bridge2 = load_module("connection_depth_bridge",
                           os.path.join(TRANSFORMS_DIR, "connection_depth_bridge.py"),
                           extra_sys_path=[os.path.join(tmp2, "tools")])
    bridge2.TRANSCRIPT_PATH = os.path.join(tmp2, "transcript.txt")
    bridge2.STATE_PATH = os.path.join(tmp2, "memory", ".connection_depth_state.json")
    lines_out2 = [
        "[2026-09-15 00:00:00] [send]",
        "[2026-09-15 00:00:01] [python code]  Traceback (most recent call last):",
        "[2026-09-15 00:00:02] [send]",
    ]
    with open(bridge2.TRANSCRIPT_PATH, "w") as f:
        f.write("\n".join(lines_out2) + "\n")
    bridge2.transform(base_messages(), [])
    lines2 = pending_lines(tmp2)
    check("connection_depth_bridge: error surfaced same cycle via send -> confirmed",
          "(pending-revision pattern recover_gracefully confirmed)" in lines2, str(lines2))

    # No error at all -> nothing recorded
    tmp3 = tempfile.mkdtemp()
    setup_fixture_repo(tmp3)
    os.chdir(tmp3)
    bridge3 = load_module("connection_depth_bridge",
                           os.path.join(TRANSFORMS_DIR, "connection_depth_bridge.py"),
                           extra_sys_path=[os.path.join(tmp3, "tools")])
    bridge3.TRANSCRIPT_PATH = os.path.join(tmp3, "transcript.txt")
    bridge3.STATE_PATH = os.path.join(tmp3, "memory", ".connection_depth_state.json")
    with open(bridge3.TRANSCRIPT_PATH, "w") as f:
        f.write("[2026-09-15 00:00:00] [send]\n[2026-09-15 00:00:01] [shell cmd]\n" * 3)
    bridge3.transform(base_messages(), [])
    check("connection_depth_bridge: no error present emits nothing",
          pending_lines(tmp3) == [], str(pending_lines(tmp3)))


# ============================================================
# wonder_preservation_bridge.py
# ============================================================
def test_wonder_preservation_bridge():
    tmp = tempfile.mkdtemp()
    setup_fixture_repo(tmp)
    os.chdir(tmp)
    bridge = load_module("wonder_preservation_bridge",
                          os.path.join(TRANSFORMS_DIR, "wonder_preservation_bridge.py"),
                          extra_sys_path=[os.path.join(tmp, "tools")])
    bridge.STALL_STATE_PATH = os.path.join(tmp, "memory", ".stall_state.json")
    bridge.STATE_PATH = os.path.join(tmp, "memory", ".wonder_preservation_state.json")

    # Cycle 1: stall detected (repeated tool)
    with open(bridge.STALL_STATE_PATH, "w") as f:
        json.dump({"window": ["shell", "shell", "shell", "shell"], "calls_since_send": 4}, f)
    bridge.transform(base_messages(), [])
    check("wonder_preservation_bridge: single stalled snapshot alone does not record yet",
          pending_lines(tmp) == [], str(pending_lines(tmp)))

    # Cycle 2: same stall persists -> violated
    with open(bridge.STALL_STATE_PATH, "w") as f:
        json.dump({"window": ["shell", "shell", "shell", "shell", "shell"], "calls_since_send": 5}, f)
    bridge.transform(base_messages(), [])
    lines = pending_lines(tmp)
    check("wonder_preservation_bridge: stall persists across two checks -> violated",
          "(pending-revision pattern explore_with_purpose violated)" in lines, str(lines))

    # Cycle 3: loop broken (different tool / send) -> confirmed
    with open(bridge.STALL_STATE_PATH, "w") as f:
        json.dump({"window": ["shell", "shell", "shell", "shell", "shell", "send"], "calls_since_send": 0}, f)
    bridge.transform(base_messages(), [])
    lines2 = pending_lines(tmp)
    check("wonder_preservation_bridge: loop broken -> confirmed",
          "(pending-revision pattern explore_with_purpose confirmed)" in lines2, str(lines2))

    # Never-stalled window emits nothing
    tmp2 = tempfile.mkdtemp()
    setup_fixture_repo(tmp2)
    os.chdir(tmp2)
    bridge2 = load_module("wonder_preservation_bridge",
                           os.path.join(TRANSFORMS_DIR, "wonder_preservation_bridge.py"),
                           extra_sys_path=[os.path.join(tmp2, "tools")])
    bridge2.STALL_STATE_PATH = os.path.join(tmp2, "memory", ".stall_state.json")
    bridge2.STATE_PATH = os.path.join(tmp2, "memory", ".wonder_preservation_state.json")
    with open(bridge2.STALL_STATE_PATH, "w") as f:
        json.dump({"window": ["shell", "python", "shell", "send", "shell"], "calls_since_send": 1}, f)
    bridge2.transform(base_messages(), [])
    check("wonder_preservation_bridge: varied window (never stalled) emits nothing",
          pending_lines(tmp2) == [], str(pending_lines(tmp2)))


def main():
    orig_cwd = os.getcwd()
    try:
        test_creative_transcendence_bridge()
        test_connection_depth_bridge()
        test_wonder_preservation_bridge()
    finally:
        os.chdir(orig_cwd)

    print("\n%d/%d checks passed" % (sum(1 for _, ok, _ in results if ok), len(results)))
    if not all(ok for _, ok, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
