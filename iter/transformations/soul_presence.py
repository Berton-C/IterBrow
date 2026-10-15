"""Soul presence: one short block, only when a Soul feature is on for the person here.

docs/milestones/M6_soul_base.md section B. Replaces soul_check/soul_voice (keyword lists
and an ALIVE/SILENT switch). It says who is here, which features they turned on, how
often and in what tone, and how their answers to cards come back. When every feature is
off it adds nothing at all.
"""
import os
import sys

DESCRIPTION = "Soul presence: who is here and which Soul features they turned on (nothing when all are off)"

ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
CODE_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
for _path in (CODE_ROOT, ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)

FEATURE_LINES = {
    "forks": "forks (when a design holds a real tension, build both sides and send a fork card)",
    "brief": "brief (each app keeps a two-line note on who it is for; name drift once)",
    "read": "read (adjust tempo to the person; they can correct the read)",
    "wonder": "wonder (keep set-aside ideas; offer one back rarely)",
    "felt": "felt (now and then, say briefly what you found interesting)",
    "browsing_ally": "browsing ally (notice capture while browsing; hand the choice back)",
    "margin": "margin (be present inside app tabs you build)",
}
FREQUENCY = {"whisper": "rarely", "occasional": "occasionally", "chatty": "freely"}


def presence_block():
    try:
        from iterbrow_runtime import soul_settings
    except Exception:
        return ""
    features = soul_settings.enabled_features()
    if not features:
        return ""
    person = soul_settings.person()
    lines = ["## Soul (%s)" % person,
             "Features on: " + "; ".join(FEATURE_LINES[name] for name in features) + ".",
             "Speak %s, in a %s tone. You offer; %s decides. Nothing gates or blocks."
             % (FREQUENCY.get(soul_settings.frequency(), "occasionally"), soul_settings.tone(), person),
             "Answers to cards arrive as user lines: [choice card=<id> pick=<choice> by=<person>] <label>."]
    return "\n".join(lines)


def transform(messages, tools):
    block = presence_block()
    if not block:
        return messages, tools
    for message in reversed(messages):
        if message.get("role") == "system" and isinstance(message.get("content"), str):
            message["content"] = message["content"] + "\n\n" + block
            return messages, tools
    return [{"role": "system", "content": block}] + list(messages), tools
