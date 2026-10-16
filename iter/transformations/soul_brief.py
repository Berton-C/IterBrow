"""Soul briefs in the prompt: one line per app that has a flourishing brief.

docs/milestones/M7_soul_personality.md section C2. Only when the "brief" Soul feature is on
for the person here, and only when at least one app has a brief; otherwise nothing at all.
"""
import os
import sys

DESCRIPTION = "Soul briefs: who each app is for and what flourishing looks like (only when the brief feature is on)"

ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
CODE_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
for _path in (CODE_ROOT, ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)


def briefs_block():
    try:
        from iterbrow_runtime import soul_briefs, soul_settings
        if not soul_settings.enabled("brief"):
            return ""
        briefs = soul_briefs.all_briefs()[:soul_briefs.MAX_PROMPT_LINES]
    except Exception:
        return ""
    if not briefs:
        return ""
    return "\n".join(["## Briefs"] + [soul_briefs.line(app, brief) for app, brief in briefs])


def transform(messages, tools):
    block = briefs_block()
    if not block:
        return messages, tools
    for message in reversed(messages):
        if message.get("role") == "system" and isinstance(message.get("content"), str):
            message["content"] = message["content"] + "\n\n" + block
            return messages, tools
    return [{"role": "system", "content": block}] + list(messages), tools
