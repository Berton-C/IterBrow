"""Record one episode: the sanctioned writer of memory/recap/episode_NNNN.json.

transformations/recap.py shows a "## Recap Request" naming the span of history
to summarize; the agent reads it with the episodes tool and calls this tool
with its summary. This tool picks the next episode number (episodes are
immutable and numbered; gaps are fine), stores the time range and the logical
history records the episode covers, advances memory/recap/.recap_state, and
regenerates the tier pyramid via rebuild_tiers.
"""
import json
import os
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
from iterbrow_runtime import recap_state
from iterbrow_runtime.episodic_history import list_episodes
from iterbrow_runtime.tool_results import ToolOutput

DESCRIPTION = (
    'Record an episode summary for a span of history (answers a Recap Request): writes the next '
    "memory/recap/episode file, advances the cursor, regenerates tiers. Times default to the request's "
    'span.'
)

MAX_SUMMARY_CHARS = 1200
VALID_TYPES = {"", "fact", "belief", "value", "todo", "preference"}


def _span(start_time, end_time, request):
    """History records (start, end) and times the episode covers."""
    if request and (not start_time or start_time == request.get("start_time")) and (
            not end_time or end_time == request.get("end_time")):
        return request["start"], request["end"], request.get("start_time"), request.get("end_time")
    if start_time and end_time:
        first, last = recap_state.span_for_times(start_time, end_time)
        if first is not None:
            return first, last, start_time, end_time
    start = recap_state.read_cursor() + 1
    end = recap_state.total_records()
    if end < start:
        return None, None, start_time or None, end_time or None
    first_time, last_time = recap_state.span_times(start, end)
    return start, end, start_time or first_time, end_time or last_time


def run(summary, start_time="", end_time="", mem_type=""):
    summary = " ".join(str(summary or "").split())
    if not summary:
        return ToolOutput("FAILED: summary is required.", False, state="invalid_input")
    mem_type = str(mem_type or "").strip().lower()
    if mem_type not in VALID_TYPES:
        return ToolOutput("FAILED: mem_type must be one of fact/belief/value/todo/preference or empty.", False,
                          state="invalid_input")
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS - 3] + "..."
    start_time = str(start_time or "").strip().replace("T", " ")[:19]
    end_time = str(end_time or "").strip().replace("T", " ")[:19]

    request = recap_state.read_request()
    start, end, first_time, last_time = _span(start_time, end_time, request)
    episodes = list_episodes()
    number = recap_state.next_episode_number(episodes)
    episode = {"e": number, "s": summary}
    if mem_type:
        episode["t"] = mem_type
    if first_time:
        episode["start_time"] = first_time
    if last_time:
        episode["end_time"] = last_time
    if start is not None:
        episode["lines"] = [start, end]

    os.makedirs(recap_state.RECAP_DIR, exist_ok=True)
    name = "episode_%04d.json" % number
    path = os.path.join(recap_state.RECAP_DIR, name)
    with open(path, "x", encoding="utf-8") as handle:  # create-only: never overwrite an episode
        handle.write(json.dumps(episode, ensure_ascii=False))
        handle.flush()
        os.fsync(handle.fileno())

    cursor = recap_state.advanced_cursor(recap_state.read_cursor(), episodes + [dict(episode, _n=number)], request)
    recap_state.write_cursor(cursor)

    span = ("history records %s-%s (%s to %s)" % (start, end, first_time, last_time)
            if start is not None else "no new history records")
    stored = "SUCCESS: wrote memory/recap/%s (E%d) covering %s; recap cursor now %d; " % (name, number, span, cursor)
    try:
        import rebuild_tiers
        tiers = rebuild_tiers.rebuild(actor="record_episode")
    except Exception as error:
        # The episode is stored and the cursor advanced: do not record it again.
        return ToolOutput(stored + "WARNING: the tier pyramid could not be regenerated (%s: %s); the episode "
                          "is stored and tiers will be rebuilt automatically next cycle."
                          % (type(error).__name__, error), True)
    return ToolOutput(stored + "tiers regenerated from %d episodes." % tiers["episode_count"], True)
