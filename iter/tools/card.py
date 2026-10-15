import importlib.util
import json
import uuid
from pathlib import Path

DESCRIPTION = """Show the person a card in the sidebar with 1-3 choices; their click comes back to you as a user message "[choice card=<id> pick=<choice-id> by=<person>] <label>". kind: fork (two poles of a real tension), brief, read, offer, note. choices: list of labels or {id,label,hint}. Use rarely: a card should be worth a decision. links: optional [{label,url}] (e.g. variant tabs)."""

KINDS = ("fork", "brief", "read", "offer", "note")
TOOLS_DIR = Path(__file__).resolve().parent


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


def run(kind, title, body, choices, links=None, expires_in_s=None):
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
    card = {"id": "card-%s" % uuid.uuid4().hex[:12], "kind": kind, "title": title, "body": body, "choices": parsed}
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
        import time
        try:
            card["expires_at"] = int(time.time() * 1000 + float(expires_in_s) * 1000)
        except (TypeError, ValueError):
            return "ERROR: expires_in_s must be a number of seconds"
    _channel().send_card(card, fallback_text(title, body, parsed))
    return "CARD-SENT: %s" % card["id"]
