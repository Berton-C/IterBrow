"""OpenUI-inspired browser feature #4 (component museum, browsing side)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _component_museum as museum

DESCRIPTION = (
    "List saved component-museum entries (live-DOM patches and tab-variant generations), "
    "most recent first. Each entry has an id you can pass to museum_recall or museum_vote."
)


def run(limit="20"):
    limit = int(limit)
    records = museum.list_all(limit=limit)
    lines = []
    for rec in reversed(records):
        css_len = len(museum.full_field(rec, "css"))
        js_len = len(museum.full_field(rec, "js"))
        html_len = len(museum.full_field(rec, "html"))
        lines.append(
            "id=%s ts=%s label=%r source=%s vote=%s url=%s (css=%dc js=%dc html=%dc)" % (
                rec.get("id"), rec.get("ts"), rec.get("label"), rec.get("source"),
                rec.get("vote"), rec.get("url"), css_len, js_len, html_len,
            )
        )
    return "\n".join(lines) if lines else "(component museum is empty)"
