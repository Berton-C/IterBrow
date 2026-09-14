"""OpenUI-inspired browser feature #4 (component museum, restore side).

Re-applies a stored component's CSS/JS onto the CURRENT live page (via the
same injection path as browser_patch_live), so a museum entry is not just
inspectable but actually restorable - closing the loop on "never lost to
being only in injected DOM."
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _component_museum as museum
import browser_patch_live

DESCRIPTION = (
    "Recall a saved component-museum entry by id and re-apply its CSS/JS onto the current "
    "live/attached tab (or a specific tab_id), restoring a previously injected UI patch. Use "
    "museum_list to find ids."
)


def run(component_id, tab_id=""):
    record = museum.get(component_id)
    if not record:
        return "ERROR: no museum entry found for id=%r" % (component_id,)

    css = museum.full_field(record, "css")
    js = museum.full_field(record, "js")
    if not css and not js:
        return "ERROR: museum entry %r has no css/js payload to re-apply (source=%s, may be an html-only tab variant - open %s directly instead)" % (
            component_id, record.get("source"), record.get("url"),
        )

    return browser_patch_live.run(
        css=css, js=js, tab_id=tab_id,
        patch_id="recall-" + component_id,
        label="recalled: " + record.get("label", component_id),
    )
