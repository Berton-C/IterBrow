"""
Recap / Episode Summarization System.

Episodes are written BY THE AGENT. This transformation decides when one is
due and tells the agent - in the system message it actually sees - exactly
how to write it; it also injects the newest episodes.

How it works:
1. The recap cursor (memory/recap/.recap_state, an integer) is the number of
   logical history records (archived history + history.metta tail) already
   summarized into episodes.
2. The cursor advances when episodes covering the requested span exist
   (record_episode stores "lines": [start, end]; any episode numbered at or
   above the requested number also completes the request).
3. A backlog larger than RECAP_MAX_PENDING_SPANS spans is skipped only once,
   at the legacy cursor migration; in normal running a large backlog gets a
   coarser span (up to RECAP_COARSE_MAX_SPAN records or one calendar day),
   read with episodes(..., conversation_only=true). History is never skipped.
4. When at least RECAP_THRESHOLD records are unsummarized, a "## Recap
   Request" block naming the episode number/file, the fields and the span by
   TIMESTAMP (the episodes tool searches by time) is appended to the system
   message, and memory/recap/.recap_needed + .recap_request.json are written.
   They are cleared as soon as the cursor catches up.
5. The newest RECAP_INJECT_EPISODES episodes are injected as a recap block.
"""
import os, json
from iterbrow_runtime.atomspace_store import _atomic_text
from iterbrow_runtime.episodic_history import list_episodes, chronological
from iterbrow_runtime import recap_state

DESCRIPTION = "Episode recap: asks the agent to record an episode (record_episode) when enough history is unsummarized, and injects the newest episodes."

HISTORY_PATH = recap_state.HISTORY_PATH
RECAP_DIR = recap_state.RECAP_DIR
STATE_PATH = recap_state.STATE_PATH
FLAG_PATH = recap_state.FLAG_PATH
REQUEST_PATH = recap_state.REQUEST_PATH

# Minimum lines of new history before triggering a recap
RECAP_THRESHOLD = 20
# One episode normally covers at most this many history records (a backlog is
# summarized span by span instead of in one unreadable request).
RECAP_MAX_SPAN = 200
# Backlog (in spans) above which the ONE-TIME cursor migration may skip older
# history (it stays searchable via search_transcript/episodes). In normal
# running nothing is ever skipped: a larger backlog gets a coarser span.
RECAP_MAX_PENDING_SPANS = 3
# A coarse span (large backlog during normal running) grows with the backlog,
# up to this many records or one calendar day, whichever is smaller -- never
# below RECAP_MAX_SPAN. The agent reads it filtered to the conversation.
RECAP_COARSE_MAX_SPAN = 1000
# Only the NEWEST episodes are injected; older ones live on in the tier pyramid.
RECAP_INJECT_EPISODES = 10
RECAP_END = "(end of episode recap)"  # must match zz_context_budget.RECAP_END
REQUEST_HEADING = "## Recap Request"


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _request_text(request, remaining):
    n = request["next_e"]
    first, last = request.get("start_time") or "?", request.get("end_time") or "?"
    if request["end"] - request["start"] + 1 > RECAP_MAX_SPAN:
        read = ("1. This is a large backlog, so the episode is coarse (a whole busy period). Read only the "
                "conversation of the span: episodes(time_string=\"{t0}\", end_time=\"{t1}\", "
                "conversation_only=true) -- user messages, your replies and send calls, not tool "
                "chatter. Summarize what was asked, done and decided.".format(t0=first, t1=last))
    else:
        read = ("1. Read the span: episodes(time_string=\"{t0}\", k=40). The episodes tool searches history by "
                "TIMESTAMP, not by record number; repeat with later timestamps up to {t1} if needed "
                "(or episodes(time_string=\"{t0}\", end_time=\"{t1}\", conversation_only=true) for just the "
                "conversation).".format(t0=first, t1=last))
    more = (" %d more unsummarized records follow; they get their own request afterwards." % remaining
            if remaining > 0 else "")
    skipped = request.get("skipped")
    if skipped:
        more += (" Older history records %d-%d were not summarized into episodes (too large a backlog); "
                 "they are still available via search_transcript and episodes." % tuple(skipped))
    return "\n".join([
        REQUEST_HEADING,
        "History records {a}-{b} ({t0} to {t1}) are not yet summarized into an episode.{more}".format(
            a=request["start"], b=request["end"], t0=first, t1=last, more=more),
        "When no user request is waiting (user work comes first), write episode E{n}:".format(n=n),
        read,
        "2. Record it: record_episode(summary=\"<2-4 sentences: what was asked, what you did, the outcome>\", "
        "start_time=\"{t0}\", end_time=\"{t1}\", mem_type=\"\")".format(t0=first, t1=last),
        "   It creates memory/recap/episode_{n:04d}.json = {{\"e\": {n}, \"s\": summary, \"t\": mem_type, "
        "\"start_time\": ..., \"end_time\": ..., \"lines\": [{a}, {b}]}}, advances the recap cursor and "
        "regenerates the tier pyramid.".format(n=n, a=request["start"], b=request["end"]),
        "Use record_episode only: never write episode files or memory/tiers/ with python/shell "
        "(existing episodes are immutable).",
    ])


def _check_recap_needed(episodes):
    """Advance the cursor over recorded episodes; return the request text to
    show the agent, or "" when no recap is due (flag files cleared)."""
    total = recap_state.total_records(HISTORY_PATH)
    migrated = recap_state.migrate_cursor(episodes, HISTORY_PATH) is not None
    stored = recap_state.read_cursor()
    previous = request = recap_state.read_request()
    cursor = recap_state.advanced_cursor(stored, episodes, request)
    skipped = None
    if migrated and total - cursor > RECAP_MAX_PENDING_SPANS * RECAP_MAX_SPAN:
        # ONE-TIME catch-up when the legacy cursor is first migrated. Never in
        # normal running: a busy period must not permanently skip history.
        skipped = [cursor + 1, total - RECAP_MAX_PENDING_SPANS * RECAP_MAX_SPAN]
        cursor = skipped[1]
    elif previous and previous.get("skipped") and previous["start"] == cursor + 1:
        skipped = previous["skipped"]  # still the request that follows the skip
    if cursor != stored:
        recap_state.write_cursor(cursor)

    if total - cursor < RECAP_THRESHOLD:
        _remove(FLAG_PATH)
        _remove(REQUEST_PATH)
        return ""

    backlog = total - cursor
    start = cursor + 1
    if backlog > RECAP_MAX_PENDING_SPANS * RECAP_MAX_SPAN:
        # Large backlog in normal running: one coarser episode instead of
        # skipping -- the span grows with the backlog (<= one calendar day).
        coarse = min(RECAP_COARSE_MAX_SPAN, max(RECAP_MAX_SPAN, backlog // RECAP_MAX_PENDING_SPANS))
        end = recap_state.span_end(start, total, coarse, RECAP_MAX_SPAN, HISTORY_PATH)
    else:
        end = min(total, cursor + RECAP_MAX_SPAN)
    start_time, end_time = recap_state.span_times(start, end, HISTORY_PATH)
    request = {"next_e": recap_state.next_episode_number(episodes), "start": start, "end": end,
               "start_time": start_time, "end_time": end_time}
    if skipped:
        request["skipped"] = skipped
    text = _request_text(request, total - end)
    if recap_state.read_request() != request:
        _atomic_text(REQUEST_PATH, json.dumps(request))
        _atomic_text(FLAG_PATH, text + "\n")
    return text


def _load_episodes():
    """All episode records in numeric episode order (not file-name order)."""
    return list_episodes(RECAP_DIR)

def _format_recap_block(episodes):
    """Format episodes into a compact summary block for system message.

    Real on-disk schema (verified against live episode_*.json): {"e" or
    "id": episode_number, "s": short_summary, optional "t": type}. Falls
    back to the older, more verbose {title, start_time, ...} shape too, in
    case any episode was ever written in that form."""
    if not episodes:
        return ""

    # Newest by the time they cover, not by number (an episode written late
    # about an earlier period is not the most recent).
    episodes = chronological(episodes)
    shown = episodes[-RECAP_INJECT_EPISODES:]
    if len(shown) == len(episodes):
        lines = ["## Episode Recap ({} episodes)".format(len(episodes))]
    else:
        lines = ["## Episode Recap (newest {} of {} episodes)".format(len(shown), len(episodes))]
    for ep in shown:
        num = ep.get("_n") if ep.get("_n") is not None else ep.get("e", ep.get("id", "?"))
        summary = ep.get("s", ep.get("summary", ""))
        mem_type = ep.get("t", "")
        title = ep.get("title", "")

        header = "### E{}".format(num)
        if title:
            header += ": {}".format(title)
        if mem_type:
            header += " [{}]".format(mem_type)
        lines.append(header)
        if summary:
            lines.append(summary)

        themes = ep.get("themes", [])
        if themes:
            lines.append("Themes: {}".format(", ".join(themes)))

        notable = ep.get("notable_steps", [])
        if notable:
            for step in notable[:3]:  # max 3 per episode
                lines.append("  - {}".format(step))
        lines.append("")

    # End sentinel: zz_context_budget's dedup removes exactly this block.
    lines.append(RECAP_END)
    return "\n".join(lines)

def _append(messages, block):
    first_msg = messages[0]
    if isinstance(first_msg, dict):
        content = first_msg.get("content", "")
        if isinstance(content, str):
            first_msg["content"] = content.rstrip() + "\n\n" + block
        elif isinstance(content, list):
            first_msg["content"] = content + [{"type": "text", "text": "\n\n" + block}]


def transform(messages, tools):
    if not messages:
        return messages, tools
    blocks = []
    try:
        os.makedirs(RECAP_DIR, exist_ok=True)
        episodes = _load_episodes()
        if episodes:
            blocks.append(_format_recap_block(episodes))
        try:
            request = _check_recap_needed(episodes)
        except Exception as error:
            request = "%s\n[recap.py could not evaluate the recap cursor: %s: %s]" % (
                REQUEST_HEADING, type(error).__name__, error)
        if request:
            # After the recap block's end sentinel: never deduplicated with it.
            blocks.append(request)
    except Exception as error:
        blocks.append("[recap.py failed: %s: %s]" % (type(error).__name__, error))
    for block in blocks:
        if block:
            _append(messages, block)
    return messages, tools
