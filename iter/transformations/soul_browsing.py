"""Soul browsing: what the person has been browsing lately, for the browsing ally.

docs/milestones/M9_soul_wonder_ally.md section C4. Only when the person turned "browsing_ally" on
and is not in quiet mode. Reads .runtime/browsing_log.jsonl (written by main.js only while the
feature is on; never for locked or app tabs) and adds the last half hour as domains with dwell
minutes, plus the one rule the ally works by: offer a pause only when a declared pair is live in
what they are doing, hand the choice back, and otherwise say nothing.
"""
import json
import os
import sys
import time
from pathlib import Path

DESCRIPTION = "Soul browsing: the last 30 minutes of browsing for the ally (only when browsing_ally is on)"

ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
CODE_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
for _path in (CODE_ROOT, ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)

WINDOW_MS = 30 * 60 * 1000
LIMIT = 8
RULE = ("Offer a pause card (kind offer, topic ally:<pair>) only when a declared pair is live in what they are "
        "doing: ally:wonder-time (WonderPreservation / TimeCoherence) or ally:wonder-shared (WonderPreservation / "
        "SharedUnderstanding), then hand the choice back; otherwise say nothing. At most one ally card per 30 min, and "
        "none while one is waiting.")


def recent_browsing(lines, now, window_ms=WINDOW_MS, limit=LIMIT):
    """[{domain, minutes, title}] newest first, dwell merged per consecutive domain (as browsing_ally.js)."""
    valid = sorted((l for l in lines if isinstance(l, dict) and l.get("domain")
                    and isinstance(l.get("at"), (int, float)) and l["at"] <= now), key=lambda l: l["at"])
    # The page they are on now always counts, however long ago they arrived (a long stay on one
    # page is the very thing the ally is for).
    latest = valid[-1] if valid else None
    recent = [l for l in valid if l["at"] >= now - window_ms or l is latest]
    runs = []
    for index, line in enumerate(recent):
        end = recent[index + 1]["at"] if index + 1 < len(recent) else now
        dwell = max(0, end - line["at"])
        if runs and runs[-1]["domain"] == line["domain"]:
            runs[-1]["ms"] += dwell
            runs[-1]["title"] = line.get("title") or runs[-1]["title"]
        else:
            runs.append({"domain": line["domain"], "ms": dwell, "title": line.get("title") or ""})
    return [{"domain": r["domain"], "minutes": int(round(r["ms"] / 60000.0)), "title": r["title"]} for r in reversed(runs)][:limit]


def _log_lines():
    path = Path(ROOT) / ".runtime" / "browsing_log.jsonl"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for raw in text.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
    return out


def browsing_block(now=None):
    try:
        from iterbrow_runtime import soul_settings
        if not soul_settings.enabled("browsing_ally") or soul_settings.mode() == "quiet":
            return ""
    except Exception:
        return ""
    recent = recent_browsing(_log_lines(), int(now if now is not None else time.time() * 1000))
    if not recent:
        return ""
    lines = ["## Browsing (ally)"]
    lines += ["%s · %d min · %s" % (r["domain"], r["minutes"], " ".join(str(r["title"]).split())[:80]) for r in recent]
    lines.append(RULE)
    return "\n".join(lines)


def transform(messages, tools):
    block = browsing_block()
    if not block:
        return messages, tools
    for message in reversed(messages):
        if message.get("role") == "system" and isinstance(message.get("content"), str):
            message["content"] = message["content"] + "\n\n" + block
            return messages, tools
    return [{"role": "system", "content": block}] + list(messages), tools
