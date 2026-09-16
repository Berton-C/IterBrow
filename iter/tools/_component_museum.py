"""Component museum storage (OpenUI-inspired fix #4 - highest priority).

NOT a tool itself (leading underscore -> tool loader ignores this file).

Root problem this fixes: live-injected UI (CSS/JS patched directly into a
real attached page via CDP/eval) only ever existed inside the page's live
DOM. Once the tab closed or navigated away, the actual generated
HTML/CSS/JS payload was gone - only a text description of it might survive
in transcript/recap, never the artifact itself (the "Stations UI loss"
incident this session). This module gives every live-DOM patch and every
generated tab-variant a permanent, content-addressed record: the actual
markup/CSS/JS bytes, not just a description of them.

Storage: memory/component_museum.jsonl (append-only, one JSON object per
line, in the same spirit as memory_journal.py) plus a companion small
sidecar dir memory/component_museum/<id>/ holding the raw html/css/js/
screenshot files for anything too big to want inline in the jsonl line.
"""

import json
import os
import sys
import time
import uuid

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _memory_guard as guard

# Anchored to project root (parent of tools/) so lookups work from any cwd.
# Root cause of the museum_vote 4/4 failures: relative paths only resolved
# when cwd == project root; every vote from another cwd died with
# "no museum entry found". (Fix applied 2026-09-14, user-approved.)
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TOOLS_DIR)
MUSEUM_LOG = os.path.join(_PROJECT_ROOT, "memory", "component_museum.jsonl")
MUSEUM_DIR = os.path.join(_PROJECT_ROOT, "memory", "component_museum")

INLINE_LIMIT = 4000  # keep the jsonl line itself small; bigger payloads go to sidecar files


def _ts():
    t = time.localtime()
    return "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])


def _new_id():
    return "comp-" + uuid.uuid4().hex[:12]


def save(label, url="", tab_id="", css="", js="", html_snapshot="", screenshot_path="", memory_item_id="", source="live_patch"):
    """Persist one component snapshot. Returns the full record dict."""
    comp_id = _new_id()
    os.makedirs(MUSEUM_DIR, exist_ok=True)
    sidecar_dir = os.path.join(MUSEUM_DIR, comp_id)

    record = {
        "id": comp_id,
        "ts": _ts(),
        "label": label or "untitled component",
        "url": url,
        "tab_id": tab_id,
        "source": source,  # "live_patch" | "tab_variant" | "manual"
        "vote": None,
        "memory_item_id": memory_item_id,
    }

    for field, content in (("css", css), ("js", js), ("html", html_snapshot)):
        if not content:
            record[field] = ""
            record[field + "_path"] = ""
            continue
        if len(content) <= INLINE_LIMIT:
            record[field] = content
            record[field + "_path"] = ""
        else:
            os.makedirs(sidecar_dir, exist_ok=True)
            fpath = os.path.join(sidecar_dir, field + (".css" if field == "css" else ".js" if field == "js" else ".html"))
            with open(fpath, "w") as f:
                f.write(content)
            record[field] = content[:200] + "...[stored in full at %s]" % fpath
            record[field + "_path"] = fpath

    if screenshot_path and os.path.exists(screenshot_path):
        os.makedirs(sidecar_dir, exist_ok=True)
        dest = os.path.join(sidecar_dir, "screenshot.png")
        try:
            with open(screenshot_path, "rb") as src, open(dest, "wb") as dst:
                dst.write(src.read())
            record["screenshot_path"] = dest
        except Exception:
            record["screenshot_path"] = ""
    else:
        record["screenshot_path"] = ""

    with guard.allow_protected_write("component_museum.save"):
        with open(MUSEUM_LOG, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    try:
        import memory_journal
        memory_journal.log("component_museum", "saved", {"id": comp_id, "label": record["label"], "source": source})
    except Exception:
        pass

    return record


def _load_all():
    if not os.path.exists(MUSEUM_LOG):
        return []
    out = []
    with open(MUSEUM_LOG, "r") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except Exception:
                continue
    return out


def list_all(limit=30):
    return _load_all()[-limit:]


def get(comp_id):
    """Latest record matching comp_id (later lines - e.g. vote updates -
    override earlier ones for the same id, append-only log style)."""
    match = None
    for rec in _load_all():
        if rec.get("id") == comp_id:
            match = rec
    return match


def full_field(record, field):
    """Resolve a field back to its full content even if it was spilled to
    a sidecar file (e.g. record['html_path'])."""
    path = record.get(field + "_path")
    if path and os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return record.get(field, "")


def update_vote(comp_id, vote, memory_item_id=None):
    """Append a new record for the same id with the vote (and optionally
    memory_item_id) set - append-only, never edits the original line in
    place; get() always resolves to the latest line for a given id."""
    original = get(comp_id)
    if not original:
        return None
    updated = dict(original)
    updated["vote"] = vote
    if memory_item_id:
        updated["memory_item_id"] = memory_item_id
    updated["ts"] = _ts()
    with guard.allow_protected_write("component_museum.update_vote"):
        with open(MUSEUM_LOG, "a") as f:
            f.write(json.dumps(updated, ensure_ascii=False) + "\n")
    return updated
