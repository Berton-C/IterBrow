"""Manual verification for provenance_guard.py -- 2026-09-14.
Run directly: python3 transformations/_test_provenance_guard.py
from the iter/ directory. Builds a temp cwd shaped like the real iter/ root
(a stub iter.py with real glob patterns, tools/_provenance.py, and
tools/support.py + tools/contradict.py as the real key producers) so
hot_dirs() and unproduced_keys() resolve exactly like they do for real.

Case 1 below reconstructs the actual 2026-09-14 incident (refresh_beliefs_fc.py's
known bugs: written at iter/ root instead of transformations/, reading
metadata.get('stv', ...) which nothing in the repo ever writes) as a
regression fixture -- the original buggy file was gitignored/live-Mac-only
and is not itself preserved, so this reconstructs its two documented bugs
from the incident writeup rather than replaying byte-identical content.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

REPO_ITER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD_PATH = os.path.join(REPO_ITER, "transformations", "provenance_guard.py")
PROV_PATH = os.path.join(REPO_ITER, "tools", "_provenance.py")

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " - " + name + ((" :: " + detail) if detail and not cond else ""))


STUB_ITER_PY = (
    'from pathlib import Path\n'
    'def load_tools():\n'
    '    return [p for p in sorted(Path("tools").glob("*.py")) if not p.name.startswith("_")]\n'
    'def apply_transformation(messages, tools):\n'
    '    for path in sorted(Path("transformations").glob("*.py")):\n'
    '        pass\n'
)

STUB_SUPPORT_PY = (
    'def run(memory_id):\n'
    '    metadata = {}\n'
    '    s1 = metadata.get("strength", 1.0)\n'
    '    c1 = metadata.get("confidence", 0.5)\n'
    '    metadata["strength"] = s1\n'
    '    metadata["confidence"] = c1\n'
)

STUB_CONTRADICT_PY = (
    'def run(memory_id):\n'
    '    metadata = {}\n'
    '    s1 = metadata.get("strength", 1.0)\n'
    '    c1 = metadata.get("confidence", 0.5)\n'
    '    metadata["strength"] = s1\n'
    '    metadata["confidence"] = c1\n'
)

# Reconstruction of refresh_beliefs_fc.py's two documented bugs: written at
# iter/ root (never transformations/), reads metadata.get('stv', (0, 0)),
# a key nothing in support.py/contradict.py ever writes.
BUGGY_SCRIPT = (
    '"""Refresh beliefs_layer.html f/c meters from real memory evidence."""\n'
    'DESCRIPTION = "Refresh belief meters"\n'
    'import json\n'
    'def transform(messages, tools):\n'
    '    with open("chroma_db/memories.json") as f:\n'
    '        data = json.load(f)\n'
    '    for metadata in data.get("metadatas", []):\n'
    '        stv = metadata.get("stv", (0, 0))\n'
    '        print(stv)\n'
    '    return messages, tools\n'
)

GOOD_SCRIPT = (
    '"""Refresh beliefs_layer.html f/c meters from real memory evidence."""\n'
    'DESCRIPTION = "Refresh belief meters"\n'
    'import json\n'
    'def transform(messages, tools):\n'
    '    with open("chroma_db/memories.json") as f:\n'
    '        data = json.load(f)\n'
    '    for metadata in data.get("metadatas", []):\n'
    '        f_val = metadata.get("strength", 0.0)\n'
    '        c_val = metadata.get("confidence", 0.0)\n'
    '        print(f_val, c_val)\n'
    '    return messages, tools\n'
)

UNRELATED_SCRIPT = (
    '"""Just a helper, not a hook, not touching shared metadata state."""\n'
    'def add(a, b):\n'
    '    return a + b\n'
)


def load_guard(tmpdir):
    spec = importlib.util.spec_from_file_location("provenance_guard", GUARD_PATH)
    mod = importlib.util.module_from_spec(spec)
    # Ensure the module's own sys.path insert of ../tools resolves inside
    # tmpdir, not the real repo -- point it explicitly before exec.
    sys.path.insert(0, os.path.join(tmpdir, "tools"))
    if "_provenance" in sys.modules:
        del sys.modules["_provenance"]
    spec.loader.exec_module(mod)
    mod.STATE_PATH = os.path.join(tmpdir, "memory", ".provenance_guard_state.json")
    return mod


def setup_fixture_repo(tmpdir):
    os.makedirs(os.path.join(tmpdir, "tools"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "transformations"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "memory"), exist_ok=True)
    with open(os.path.join(tmpdir, "iter.py"), "w") as f:
        f.write(STUB_ITER_PY)
    with open(os.path.join(tmpdir, "tools", "support.py"), "w") as f:
        f.write(STUB_SUPPORT_PY)
    with open(os.path.join(tmpdir, "tools", "contradict.py"), "w") as f:
        f.write(STUB_CONTRADICT_PY)
    shutil.copy(PROV_PATH, os.path.join(tmpdir, "tools", "_provenance.py"))
    with open(os.path.join(tmpdir, "nace_pending.metta"), "w") as f:
        f.write(";; NACE Pending\n")


def shell_write_message(path, body, call_id):
    cmd = "cat > %s <<'EOF'\n%s\nEOF" % (path, body)
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": call_id, "function": {"name": "shell", "arguments": json.dumps({"cmd": cmd})}}],
    }


def base_messages():
    return [{"role": "system", "content": "system prompt"}]


def pending_lines(tmpdir):
    with open(os.path.join(tmpdir, "nace_pending.metta")) as f:
        return [l.strip() for l in f if l.strip().startswith("(pending-revision")]


def main():
    tmp1 = tempfile.mkdtemp()
    setup_fixture_repo(tmp1)
    os.chdir(tmp1)
    guard = load_guard(tmp1)

    # --- Case 1: reconstructed real incident -- misplaced (iter/ root, not
    # transformations/) AND wrong key (stv, never produced) ---
    messages = base_messages() + [shell_write_message("refresh_beliefs_fc.py", BUGGY_SCRIPT, "call_1")]
    new_messages, new_tools = guard.transform(list(messages), [])
    sys_note = new_messages[0]["content"]
    check("Case 1: violation note appended for misplaced+bad-key script",
          "Provenance Guard" in sys_note, sys_note)
    check("Case 1: flags the wrong-directory (misplaced hook) reason",
          "not inside any real auto-loaded directory" in sys_note, sys_note)
    check("Case 1: flags the unproduced key (stv)",
          "'stv'" in sys_note, sys_note)
    lines = pending_lines(tmp1)
    check("Case 1: emits a real 'violated' pending-revision for verify_before_claiming",
          "(pending-revision pattern verify_before_claiming violated)" in lines, str(lines))

    # --- Case 2: correctly-placed, correctly-keyed script -> confirmed, no note ---
    tmp2 = tempfile.mkdtemp()
    setup_fixture_repo(tmp2)
    os.chdir(tmp2)
    guard2 = load_guard(tmp2)
    messages2 = base_messages() + [shell_write_message(
        "transformations/dashboard_beliefs_refresh.py", GOOD_SCRIPT, "call_2")]
    new_messages2, _ = guard2.transform(list(messages2), [])
    check("Case 2: no violation note for correctly-placed, correctly-keyed script",
          "Provenance Guard" not in new_messages2[0]["content"], new_messages2[0]["content"])
    lines2 = pending_lines(tmp2)
    check("Case 2: emits a real 'confirmed' pending-revision, not 'violated'",
          "(pending-revision pattern verify_before_claiming confirmed)" in lines2
          and "violated" not in "".join(lines2), str(lines2))

    # --- Case 3: unrelated, non-hook, non-metadata script -> skipped entirely ---
    tmp3 = tempfile.mkdtemp()
    setup_fixture_repo(tmp3)
    os.chdir(tmp3)
    guard3 = load_guard(tmp3)
    messages3 = base_messages() + [shell_write_message("tools/mathutil.py", UNRELATED_SCRIPT, "call_3")]
    new_messages3, _ = guard3.transform(list(messages3), [])
    check("Case 3: unrelated script triggers no note",
          "Provenance Guard" not in new_messages3[0]["content"], new_messages3[0]["content"])
    check("Case 3: unrelated script emits no pending-revision at all",
          pending_lines(tmp3) == [], str(pending_lines(tmp3)))

    # --- Case 4: idempotency -- running transform() twice on the same
    # already-processed call must not double-emit ---
    os.chdir(tmp1)
    guard4 = load_guard(tmp1)
    before = pending_lines(tmp1)
    guard4.transform(list(messages), [])  # same call_id as Case 1, already processed
    after = pending_lines(tmp1)
    check("Case 4: idempotent -- re-processing the same call_id does not re-emit",
          before == after, "before=%s after=%s" % (before, after))

    # --- Case 5: fail-open -- a script written into a directory the loader
    # DOES scan (so it's not flagged as misplaced) but iter.py itself is
    # missing/unreadable must not crash and must fall back sanely ---
    tmp5 = tempfile.mkdtemp()
    setup_fixture_repo(tmp5)
    os.remove(os.path.join(tmp5, "iter.py"))
    os.chdir(tmp5)
    guard5 = load_guard(tmp5)
    messages5 = base_messages() + [shell_write_message(
        "transformations/dashboard_beliefs_refresh.py", GOOD_SCRIPT, "call_5")]
    try:
        new_messages5, _ = guard5.transform(list(messages5), [])
        crashed = False
    except Exception as e:
        crashed = True
        new_messages5 = None
    check("Case 5: fail-open when iter.py is missing (falls back to known-true dirs, never raises)",
          not crashed, "crashed" if crashed else "")

    print("\n%d/%d checks passed" % (sum(1 for _, ok, _ in results if ok), len(results)))
    if not all(ok for _, ok, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
