import importlib.util
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

DESCRIPTION = """Show the person a sidebar card with 1-3 choices; their click returns as "[choice card=<id> pick=<choice> by=<person>] <label>". kind: fork, brief, read, offer, note. choices: labels or {id,label,hint,pattern,museum_id}: pattern = the Soul pattern that pole protects (lets Iter learn the person's leans), museum_id = the variant it picks (the pick casts keep/reject). links: optional [{label,url}]. topic: wonder:<id>, growth or ally:<pair> when the card answers one. Use rarely."""

KINDS = ("fork", "brief", "read", "offer", "note")
TOOLS_DIR = Path(__file__).resolve().parent
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
for _path in (str(TOOLS_DIR.parent), ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)
IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
MUSEUM_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def _channel():
    # The channel lives beside tools/ in the live tree (or the hot-load generation).
    path = TOOLS_DIR.parent / "channels" / "electron_ui.py"
    spec = importlib.util.spec_from_file_location("electron_ui_channel_for_card", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _as_list(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = [part.strip() for part in value.split("|") if part.strip()]
    return value if isinstance(value, list) else None


def _choices(raw):
    items = _as_list(raw)
    if items is None:
        return None, "choices must be a list"
    out = []
    for index, item in enumerate(items):
        if isinstance(item, str):
            item = {"label": item}
        if not isinstance(item, dict) or not str(item.get("label", "")).strip():
            return None, "every choice needs a label"
        default_id = "abc"[index] if index < 3 else str(index)
        choice = {"id": str(item.get("id") or default_id).strip(),
                  "label": str(item["label"]).strip()}
        if item.get("hint"):
            choice["hint"] = str(item["hint"]).strip()
        if item.get("pattern"):
            pattern = str(item["pattern"]).strip()
            if not IDENT.match(pattern):
                return None, "unknown pattern %r" % pattern
            choice["pattern"] = pattern
        if item.get("museum_id"):
            museum_id = str(item["museum_id"]).strip()
            if not MUSEUM_ID.match(museum_id):
                return None, "museum_id must be a component-museum id"
            choice["museum_id"] = museum_id
        out.append(choice)
    if not 1 <= len(out) <= 3:
        return None, "a card has 1 to 3 choices (got %d)" % len(out)
    ids = [choice["id"] for choice in out]
    if len(set(ids)) != len(ids) or "dismiss" in ids:
        return None, "choice ids must be distinct and not 'dismiss'"
    return out, None


def fallback_text(title, body, choices):
    lines = ["**%s**" % title]
    if body:
        lines += ["", body]
    lines.append("")
    for index, choice in enumerate(choices, 1):
        lines.append("%d. %s%s" % (index, choice["label"], (" — " + choice["hint"]) if choice.get("hint") else ""))
    return "\n".join(lines)


def _atomspace():
    from iterbrow_runtime.cognitive_events import _call_atomspace
    return _call_atomspace


def _known_patterns():
    """The nine pattern names, read from the kernel atoms (never a Python list). None = unreachable."""
    try:
        from iterbrow_runtime import soul_lens
        return set(soul_lens.patterns())
    except Exception:
        return None


def _person():
    try:
        from iterbrow_runtime import soul_settings
        return soul_settings.person()
    except Exception:
        return "guest"


def _quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def offer_operations(card, person, at_ms):
    """soul-card and soul-card-choice atoms (docs/milestones/M7_soul_personality.md A1)."""
    ops = [{"op": "upsert", "key": "state:soul_card:%s" % card["id"],
            "atom": "(soul-card %s %s %s %d)" % (_quote(card["id"]), _quote(card["kind"]), _quote(person), at_ms)}]
    for choice in card["choices"]:
        ops.append({"op": "upsert", "key": "state:soul_card_choice:%s:%s" % (card["id"], choice["id"]),
                    "atom": "(soul-card-choice %s %s %s %s)" % (_quote(card["id"]), _quote(choice["id"]),
                                                             choice.get("pattern") or "none",
                                                             _quote(choice.get("museum_id") or "-"))})
    if card.get("topic"):
        ops.append({"op": "upsert", "key": "state:soul_card_topic:%s" % card["id"],
                    "atom": "(soul-card-topic %s %s)" % (_quote(card["id"]), _quote(card["topic"]))})
    return ops


TOPIC = re.compile(r"^[a-z][a-z0-9_:-]{0,63}$")


def run(kind, title, body, choices, links=None, expires_in_s=None, topic=None):
    kind = str(kind or "").strip()
    title = str(title or "").strip()
    body = str(body or "").strip()
    if kind not in KINDS:
        return "ERROR: kind must be one of %s" % ", ".join(KINDS)
    if not title:
        return "ERROR: a card needs a title"
    parsed, error = _choices(choices)
    if error:
        return "ERROR: %s" % error
    named = sorted({c["pattern"] for c in parsed if c.get("pattern")})
    known = _known_patterns() if named else set()
    if known is not None:
        unknown = [name for name in named if name not in known]
        if unknown:
            return "ERROR: unknown pattern %s (the nine are in the Soul kernel; soul_reflect lists them)" % ", ".join(unknown)
    topic = str(topic or "").strip() or None
    if topic and not TOPIC.match(topic):
        return "ERROR: topic must look like wonder:<id>, growth or ally:<pair>"
    card = {"id": "card-%s" % uuid.uuid4().hex[:12], "kind": kind, "title": title, "body": body, "choices": parsed}
    if topic:
        card["topic"] = topic
    if links:
        link_list = _as_list(links) or []
        clean = [{"label": str(l.get("label", "")).strip(), "url": str(l.get("url", "")).strip()}
                 for l in link_list if isinstance(l, dict)]
        clean = [l for l in clean if l["label"] and l["url"].lower().startswith(("http://", "https://"))]
        if len(clean) != len(link_list) or len(clean) > 3:
            return "ERROR: links must be up to 3 {label, url} with http(s) urls"
        if clean:
            card["links"] = clean
    if expires_in_s:
        try:
            card["expires_at"] = int(time.time() * 1000 + float(expires_in_s) * 1000)
        except (TypeError, ValueError):
            return "ERROR: expires_in_s must be a number of seconds"
    person = _person()
    at_ms = int(time.time() * 1000)
    _channel().send_card(card, fallback_text(title, body, parsed))
    # Record what was offered, so the person's pick can teach the Soul their leans.
    # Best effort: the card has already gone out.
    if known is None:
        return "CARD-SENT: %s (unrecorded)" % card["id"]
    try:
        _atomspace()("transact", operations=offer_operations(card, person, at_ms), actor="iter", source="card")
    except Exception:
        return "CARD-SENT: %s (unrecorded)" % card["id"]
    return "CARD-SENT: %s" % card["id"]
