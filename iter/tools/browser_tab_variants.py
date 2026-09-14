"""OpenUI-inspired browser feature #3: parallel tab-variant comparison.

OpenUI generates several UI variants and shows them side by side inside
its own web app. Iter Browser can do the real-browser equivalent: open N
actual tabs, each rendering a different LLM-generated HTML/CSS/JS variant,
for genuine side-by-side comparison in the real window (reuses the same
file-backed "computable surface" mechanism as browser_build_surface.py).

Every variant is also saved into the component museum immediately (not
only if later kept) so all candidates - not just the winner - survive
past the session.
"""

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call
import _component_museum as museum

DESCRIPTION = (
    "Open N real browser tabs at once, each rendering a different LLM-generated HTML/CSS/JS "
    "UI variant, for live side-by-side comparison in the actual window (not a sandboxed "
    "preview). Pass variants as a JSON array of {label, html} objects (each html must be a "
    "full <html>...</html> document). Every variant is saved to the component museum "
    "immediately, win or lose. Returns the tab_id opened for each variant plus its museum id "
    "- use museum_vote afterwards to record which one was kept."
)

SURFACES_DIR = Path(".runtime/surfaces")


def _slug(title):
    slug = re.sub(r"[^a-z0-9-]+", "-", (title or "variant").lower()).strip("-")
    return slug or "variant"


def run(variants):
    import json
    if isinstance(variants, str):
        variants = json.loads(variants)
    if not isinstance(variants, list) or not variants:
        raise ValueError("variants must be a non-empty JSON array of {label, html} objects")

    SURFACES_DIR.mkdir(parents=True, exist_ok=True)
    opened = []
    for i, variant in enumerate(variants):
        label = variant.get("label") or ("variant-%d" % (i + 1))
        html = variant.get("html", "")
        if not html or "<html" not in html.lower():
            opened.append({"label": label, "error": "html must be a full <html>...</html> document"})
            continue

        filename = "%s-%d.html" % (_slug(label), int(time.time() * 1000) + i)
        path = (SURFACES_DIR / filename).resolve()
        path.write_text(html, encoding="utf-8")
        result = call("newTab", url="file://" + str(path))
        tab_id = result["created"]

        record = museum.save(
            label=label,
            url="file://" + str(path),
            tab_id=str(tab_id),
            html_snapshot=html,
            source="tab_variant",
        )
        opened.append({"label": label, "tab_id": tab_id, "museum_id": record["id"], "path": str(path)})

    return str(opened)
