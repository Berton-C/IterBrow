"""Manual verification for Stage 5 (completion_claim_guard.py gets real
severing power). Run from iter/: python3 transformations/_test_stage5_guard.py
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


def base_tools():
    return [
        {"type": "function", "function": {"name": "send", "description": "", "parameters": {}}},
        {"type": "function", "function": {"name": "task_state", "description": "", "parameters": {}}},
        {"type": "function", "function": {"name": "shell", "description": "", "parameters": {}}},
    ]


def has_send(tools):
    return any(t.get("function", {}).get("name") == "send" for t in tools)


def main():
    tmpdir = tempfile.mkdtemp()
    os.chdir(tmpdir)

    import completion_claim_guard as guard

    # --- Case 1: unverified completion claim, no task_state.metta present -> send withheld ---
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "assistant", "content": "The founder toolkit tab already exists and is now live.", "tool_calls": [{"function": {"name": "nop"}}]},
    ]
    new_messages, new_tools = guard.transform(list(messages), base_tools())
    check("Case 1: unverified completion claim strips send from tools",
          not has_send(new_tools), str(new_tools))
    check("Case 1: advisory note still appended to system message",
          "Completion Claim Guard" in new_messages[0]["content"], new_messages[0]["content"])

    # --- Case 2: same claim, but task_state.metta says verifying -> no stripping ---
    with open("task_state.metta", "w") as f:
        f.write('(task-phase "founder-tab" verifying)\n')
    new_messages2, new_tools2 = guard.transform(list(messages), base_tools())
    check("Case 2: claim backed by a recorded verifying phase leaves send intact",
          has_send(new_tools2), str(new_tools2))
    os.remove("task_state.metta")

    # --- Case 3: no completion claim at all -> tools untouched, no note ---
    plain_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "assistant", "content": "Still working on the founder toolkit tab.", "tool_calls": [{"function": {"name": "shell"}}]},
    ]
    new_messages3, new_tools3 = guard.transform(list(plain_messages), base_tools())
    check("Case 3: no completion claim -> send stays available",
          has_send(new_tools3), str(new_tools3))
    check("Case 3: no completion claim -> system message unchanged",
          new_messages3[0]["content"] == "system prompt", new_messages3[0]["content"])

    # --- Case 4: unverified claim AND silent_streak already near HARD_SEND_STREAK -> fail open, do NOT strip send ---
    near_streak_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "shell"}}]},
        {"role": "assistant", "content": "already exists and is now live", "tool_calls": [{"function": {"name": "nop"}}]},
    ]
    new_messages4, new_tools4 = guard.transform(list(near_streak_messages), base_tools())
    check("Case 4: near HARD_SEND_STREAK -- fails open, send NOT stripped (avoids deadlock with iter.py's check-in net)",
          has_send(new_tools4), str(new_tools4))

    # --- Case 5: malformed messages/tools never raise ---
    try:
        guard.transform("not a list", "also not a list")
        ok5 = True
    except Exception as e:
        ok5 = False
    check("Case 5: malformed input never raises (fails open, never crashes the pipeline)", ok5)

    # --- Case 6: original behavior (no claim -> completely untouched pass-through) still holds ---
    empty_result = guard.transform([], [])
    check("Case 6: empty input returns empty pass-through", empty_result == ([], []), str(empty_result))

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print("\n%d/%d checks passed" % (len(results) - n_fail, len(results)))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
