"""Beliefs Layer refresh -- keeps .runtime/pages/beliefs_layer.html's f/c meters
live against the real chroma memory records instead of a frozen hand-typed
snapshot.

Replaces the earlier one-off `refresh_beliefs_fc.py` (left at iter/ root,
never auto-invoked since it lived outside transformations/, and buggy: it
read a metadata key named "stv" that support()/contradict() never write --
they write "strength" and "confidence" directly, see tools/support.py and
tools/contradict.py). This version reads those two real fields and only
touches the file when a value actually changed, so the "f/c refreshed HH:MM"
timestamp means something.

Card -> backing LTM memory (hypothesis registry, memory 6037725c):
  H1 path-fragility        -> 505c1ac3
  H2 NAL reliability       -> d7615651
  H3 send-discipline       -> 05fbf5bd
  H4 websearch             -> 0a901d47
  H5 substrate-compounding -> dc7ca12f
"""

import json
import os
import re
import time

DESCRIPTION = ("Refreshes .runtime/pages/beliefs_layer.html's f/c meters from the real "
               "strength/confidence fields on the 5 backing chroma memories (H1-H5), "
               "instead of a static hand-typed snapshot. Fails open / no-ops on any error.")

ITER_ROOT = "."
DB_PATH = os.path.join(ITER_ROOT, "chroma_db", "memories.json")
PAGE_PATH = os.path.join(ITER_ROOT, ".runtime", "pages", "beliefs_layer.html")

# Ordered H1..H5, matched to the card that contains this literal heading text.
HYPOTHESES = [
    ("H1 &middot; Path-fragility", "505c1ac3"),
    ("H2 &middot; NAL-weighted reliability", "d7615651"),
    ("H3 &middot; Short proactive updates", "05fbf5bd"),
    ("H4 &middot; websearch:", "0a901d47"),
    ("H5 &middot; The substrate", "dc7ca12f"),
]

METER_RE = re.compile(
    r'<div class="meter">f=[\d.]+ c=[\d.]+<div class="bar"><div style="width:\d+%">'
)


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _load_stv_by_prefix():
    """Return {prefix: (f, c)} using the real strength/confidence fields.
    A memory with no strength/confidence recorded yet (true SEED, no
    support()/contradict() calls so far) maps to (None, None)."""
    with open(DB_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    ids = data.get("ids", [])
    metas = data.get("metadatas", [])
    out = {}
    prefixes = [p for _, p in HYPOTHESES]
    for i, mid in enumerate(ids):
        for prefix in prefixes:
            if mid.startswith(prefix):
                m = metas[i] or {}
                f = m.get("strength")
                c = m.get("confidence")
                out[prefix] = (
                    round(float(f), 2) if f is not None else None,
                    round(float(c), 2) if c is not None else None,
                )
    return out


def _meter_html(f, c):
    f = f if f is not None else 0.0
    c = c if c is not None else 0.0
    width = int(round(f * 100))
    return '<div class="meter">f=%.2f c=%.2f<div class="bar"><div style="width:%d%%">' % (f, c, width)


def _parse_current_meter(block):
    m = re.search(r'f=([\d.]+) c=([\d.]+)', block or "")
    if not m:
        return None
    return round(float(m.group(1)), 2), round(float(m.group(2)), 2)


def refresh():
    if not _exists(DB_PATH) or not _exists(PAGE_PATH):
        return "no-op: missing db or page"

    stv_by_prefix = _load_stv_by_prefix()

    with open(PAGE_PATH, "r", encoding="utf-8") as fh:
        html = fh.read()

    changed = False
    for heading, prefix in HYPOTHESES:
        idx = html.find(heading)
        if idx < 0:
            continue
        # Find the next card heading (or end of doc) to bound the search,
        # then the meter block within that bounded slice.
        next_idx = len(html)
        for other_heading, _ in HYPOTHESES:
            if other_heading == heading:
                continue
            j = html.find(other_heading, idx + 1)
            if j != -1 and j < next_idx:
                next_idx = j
        segment = html[idx:next_idx]
        meter_match = METER_RE.search(segment)
        if not meter_match:
            continue

        new_f, new_c = stv_by_prefix.get(prefix, (None, None))
        current = _parse_current_meter(meter_match.group(0))
        target = (new_f if new_f is not None else 0.0, new_c if new_c is not None else 0.0)
        if current == target:
            continue

        new_block = _meter_html(new_f, new_c)
        abs_start = idx + meter_match.start()
        abs_end = idx + meter_match.end()
        html = html[:abs_start] + new_block + html[abs_end:]
        changed = True

    if not changed:
        return "no-op: no belief changes since last refresh"

    now = time.strftime("%H:%M")
    html = re.sub(r'f/c refreshed \d\d:\d\d', "f/c refreshed " + now, html)

    with open(PAGE_PATH, "w", encoding="utf-8") as fh:
        fh.write(html)

    return "refreshed beliefs_layer.html meters at " + now


def transform(messages, tools):
    try:
        refresh()
    except Exception:
        pass  # dashboard refresh is never allowed to break the main loop
    return messages, tools
