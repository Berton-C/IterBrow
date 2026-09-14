"""OpenUI-inspired browser feature #5: keep/reject signal wired into NAL
truth revision (mirrors OpenUI's thumbs up/down voting on generated UIs,
but feeds a real calibration mechanism Iter already has instead of just a
UI counter).

vote="keep"   -> support.py:    positive NAL evidence on the linked memory
                 item, plus nudges the seeded calibration_accumulation
                 soul skill a step toward maturity.
vote="reject" -> contradict.py: negative NAL evidence on the linked memory
                 item.

Every museum entry gets a matching chroma memory item created lazily on
first vote (mem_type="preference", since "I liked/disliked this generated
UI" is a preference-shaped memory) so support/contradict - which both
operate on chroma item_id + episode_time - have something to act on.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _component_museum as museum
import remember
import support
import contradict
import soul_skill_registry
import memory_journal

DESCRIPTION = (
    "Record a keep/reject decision on a component-museum entry (id from museum_list). "
    "vote='keep' applies positive NAL truth-revision evidence (support.py) to the "
    "component's memory record and nudges the calibration_accumulation soul skill toward "
    "maturity; vote='reject' applies negative evidence (contradict.py). Every vote is "
    "journaled."
)


def _ts():
    t = time.localtime()
    return "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])


def _ensure_memory_item(record):
    item_id = record.get("memory_item_id")
    if item_id:
        return item_id
    desc = "Generated UI component %r (source=%s, url=%s)" % (
        record.get("label"), record.get("source"), record.get("url"),
    )
    result = remember.run(desc, provenance_type="observed", mem_type="preference")
    if result.startswith("REMEMBER-SUCCESS:"):
        item_id = result.split("stored ", 1)[1].split(" ", 1)[0]
        museum.update_vote(record["id"], record.get("vote"), memory_item_id=item_id)
        return item_id
    return ""


def run(component_id, vote):
    vote = (vote or "").strip().lower()
    if vote not in ("keep", "reject"):
        return "ERROR: vote must be 'keep' or 'reject'"

    record = museum.get(component_id)
    if not record:
        return "ERROR: no museum entry found for id=%r" % (component_id,)

    item_id = record.get("memory_item_id") or _ensure_memory_item(record)
    ts = _ts()
    nal_result = "no linked memory item"
    if item_id:
        if vote == "keep":
            nal_result = support.run(item_id, ts)
        else:
            nal_result = contradict.run(item_id, ts)

    museum.update_vote(component_id, vote, memory_item_id=item_id)

    skill_result = ""
    if vote == "keep":
        skill_result = soul_skill_registry.run(action="mature", name="calibration_accumulation")

    memory_journal.log("museum_vote", vote, {"component_id": component_id, "item_id": item_id})

    return "vote=%s component_id=%s item_id=%s\nNAL: %s\nskill: %s" % (
        vote, component_id, item_id, nal_result, skill_result,
    )
