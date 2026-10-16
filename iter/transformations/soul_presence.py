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
    "forks": "forks (declared pair → both poles via browser_tab_variants; fork card: pattern, museum_id, links)",
    "brief": "brief (two lines per app; contradicting one → a brief card once: continue / revise / drop)",
    "read": "read (match their tempo)",
    "wonder": "wonder (keep cut ideas; offer one back)",
    "felt": "felt (a short note on what you found interesting; %s)",
    "browsing_ally": "browsing ally (notice capture; hand it back)",
    "margin": 'margin ([margin …] lines from app tabs; "jam on this" → three riffs via browser_tab_variants + fork card)',
}
FREQUENCY = {"whisper": "rarely", "occasional": "occasionally", "chatty": "freely"}
# One line per non-default mode (docs/milestones/M8_soul_presence.md A3); quiet has no block at all.
MODE_LINES = {
    "jam": "Mode: jam — riff freely; playful variant names; a fork may hold three poles; felt notes welcome.",
    "critique": ("Mode: critique — walk the app as the person its brief names; report what is technically correct "
                 "and dead with soul_absent_test; change nothing."),
    "museum": ("Mode: museum night — walk kept and rejected variants with museum_night and say why, using what "
               "you've learned of their taste."),
}
MODES_HINT = "soul_mode on a word: jam, quiet, critique, museum night, open."


def _mode():
    try:
        from iterbrow_runtime import soul_settings
        return soul_settings.mode()
    except Exception:
        return "open"


def _learned(person):
    """What the Soul has learned about this person from their card answers (M7-A3), or ""."""
    try:
        from iterbrow_runtime import soul_lens
        return soul_lens.taste_line(person)
    except Exception:
        return ""


def _budget_line(budget, felt_on):
    things = "cards or felt notes" if felt_on else "cards"
    if budget <= 0:
        return "No %s unless asked." % things
    return "Up to %d %s per cycle." % (budget, things)


def presence_block():
    try:
        from iterbrow_runtime import soul_settings
    except Exception:
        return ""
    mode = _mode()
    if mode == "quiet":
        return ""
    features = soul_settings.enabled_features()
    if not features:
        return ""
    person = soul_settings.person()
    frequency = FREQUENCY.get(soul_settings.frequency(), "occasionally")
    described = [FEATURE_LINES[name] % frequency if name == "felt" else FEATURE_LINES[name] for name in features]
    lines = ["## Soul (%s)" % person,
             "On: " + "; ".join(described) + ".",
             "Speak %s, %s tone; you offer, %s decides, nothing gates. %s Picks return as "
             "[choice card=… pick=… by=…] <label>."
             % (frequency, soul_settings.tone(), person, _budget_line(soul_settings.budget(), "felt" in features)),
             MODE_LINES.get(mode, MODES_HINT)]
    learned = _learned(person)
    if learned:
        lines.append("Learned: " + learned + ".")
    return "\n".join(lines)


def _without_felt(tools):
    """The felt tool is offered only when the person turned felt on (M7-B3)."""
    return [tool for tool in tools
            if not (isinstance(tool, dict) and (tool.get("function") or {}).get("name") == "felt")]


def transform(messages, tools):
    try:
        from iterbrow_runtime import soul_settings
        felt_on = soul_settings.enabled("felt") and soul_settings.mode() != "quiet"
    except Exception:
        felt_on = False
    if not felt_on and isinstance(tools, list):
        tools = _without_felt(tools)
    block = presence_block()
    if not block:
        return messages, tools
    for message in reversed(messages):
        if message.get("role") == "system" and isinstance(message.get("content"), str):
            message["content"] = message["content"] + "\n\n" + block
            return messages, tools
    return [{"role": "system", "content": block}] + list(messages), tools
