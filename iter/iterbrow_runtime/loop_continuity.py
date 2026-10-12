"""Recover an explicit event-wait from existing experience, not inferred completion.

No new state or semantic classifier. A wait is an attention boundary, not proof
that work finished: instructions, history and the working account remain intact.
"""
import json


def event_wait_boundary(messages):
    """Latest fully successful exchange choosing nop(0), as [start, end)."""
    for start in range(len(messages) - 1, -1, -1):
        message = messages[start]
        if message.get("role") != "assistant":
            continue
        calls = message.get("tool_calls") or []
        waits = [call for call in calls if call.get("function", {}).get("name") == "nop"]
        if not waits:
            continue
        try:
            args = json.loads(waits[0]["function"]["arguments"])
            seconds = args.get("wait_seconds", 0)
            if isinstance(seconds, bool) or float(seconds) != 0:
                continue
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        end = start + 1
        while end < len(messages) and messages[end].get("role") == "tool":
            end += 1
        results = messages[start + 1:end]
        identities = {call.get("id") for call in calls}
        if (None not in identities and len(identities) == len(calls) == len(results)
                and identities == {result.get("tool_call_id") for result in results}
                and all((result.get("_iter_execution") or {}).get("success") is True
                        for result in results)):
            return start, end
    return None


def resume_event_wait(messages, heartbeat, snapshot):
    """Only restore a healthy idle wait in the SAME stable component generation.

Queued input and due alarms are checked by the existing wait loop. New or
probationary generations and interrupted/failed work take the normal startup
path. A process restart alone is not a reason to wake the model.
"""
    if not isinstance(heartbeat, dict) or not isinstance(snapshot, dict):
        return False
    boundary = event_wait_boundary(messages)
    return bool(boundary and boundary[1] == len(messages)
                and heartbeat.get("phase") == "idle_wait"
                and heartbeat.get("hard_floor_ok") is True
                and snapshot.get("status") == "stable"
                and heartbeat.get("generation_id") == snapshot.get("generation_id"))


INTERRUPTED_EXECUTION = {"success": None, "state": "not_executed", "scope": "invocation",
                         "task_fulfillment": "unverified"}


def unanswered_tool_calls(messages):
    """Tool calls of the trailing assistant turn that have no result yet."""
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.get("role") == "tool":
            continue
        if message.get("role") != "assistant":
            return []
        answered = {result.get("tool_call_id") for result in messages[index + 1:]
                    if result.get("role") == "tool"}
        return [call for call in (message.get("tool_calls") or [])
                if call.get("id") and call.get("id") not in answered]
    return []


def complete_interrupted_turn(messages, reason, timestamp):
    """Return messages plus placeholder results for calls that never ran.

    Work that already happened in this turn (a reply the user received, a tool
    that ran) is kept; the calls that were cut off by Stop, a crash or an error
    get an explicit "not executed" result so the saved history stays a valid
    request and the next cycle knows exactly what did not happen."""
    placeholders = [{
        "role": "tool",
        "tool_call_id": call["id"],
        "content": "Step " + timestamp + ": [NOT EXECUTED: " + reason + "]",
        "_iter_execution": dict(INTERRUPTED_EXECUTION),
    } for call in unanswered_tool_calls(messages)]
    return list(messages) + placeholders
