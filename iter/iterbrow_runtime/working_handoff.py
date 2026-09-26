"""Working meaning plus subsequent observations, projected from durable experience.

No second store, model call, semantic classifier or execution prerequisite. A
marked pin is the LLM's revisable account, not an authoritative state assertion.
The pin's whole response was generated before any of its tools ran, so even
results preceding the pin in that response are newer evidence.
"""
import json

from .request_budget import active_work_start, _input_text, is_user_input
from .tool_results import output_excerpt, execution_facts, RESULT_ID

MAX_HANDOFF_CHARS = 4000
MAX_OBSERVATION_CHARS = 12000


def observation_excerpt(text, identity, limit=650):
    """Show existing payload spans, not their transport wrapper; never read/replay.

    Unwrap only the matching outer retention envelope. Historical nested content
    remains exact. Offsets/omissions refer to the original timestamped output.
    Fit inside the old serialized allowance so other receipts cannot be crowded out.
    """
    fallback = output_excerpt(text, limit)
    prefix, body = "", text
    if text.startswith("Step ") and ": " in text:
        prefix, body = text.split(": ", 1)
        prefix += ": "
    try:
        envelope = json.loads(body)
    except (ValueError, TypeError, RecursionError):
        return fallback
    if (not isinstance(envelope, dict) or envelope.get("kind") != "retained_tool_output"
            or envelope.get("retained") is not True or envelope.get("tool_call_id") != identity):
        return fallback
    head, tail, total = (envelope.get(k) for k in ("preview", "tail", "text_chars"))
    result_id = envelope.get("result_id")
    if (not isinstance(head, str) or not isinstance(tail, str) or type(total) is not int
            or total < len(head) + len(tail)
            or envelope.get("tail_offset") != total - len(tail)
            or envelope.get("omitted_chars") != total - len(head) - len(tail)
            or not isinstance(result_id, str) or not RESULT_ID.fullmatch(result_id)):
        return fallback
    allowance = len(json.dumps(fallback, ensure_ascii=False))
    for budget in range(limit, 0, -32):
        if total == len(head) + len(tail):
            view = output_excerpt(prefix + head + tail, budget)
        else:
            first = (prefix + head)[:budget // 3]
            last_size = budget - len(first)
            last = tail[-last_size:] if last_size else ""
            view = {"preview": first, "tail": last,
                    "tail_offset": len(prefix) + total - len(last),
                    "omitted_chars": len(prefix) + total - len(first) - len(last)}
        view["result_id"] = result_id
        if len(json.dumps(view, ensure_ascii=False)) <= allowance:
            return view
    return fallback


def marked_handoff(arguments):
    return isinstance(arguments, dict) and (
        arguments.get("handoff") is True or arguments.get("handoff") == "true")


def working_context(experience):
    """Return bounded, explicitly attributed data; never alter saved history."""
    start = active_work_start(experience)
    calls, results = {}, {}
    for index, message in enumerate(experience):
        if index < start:
            continue
        if message.get("role") == "assistant":
            for call in message.get("tool_calls", []) or []:
                calls[call.get("id")] = (index, call.get("function", {}))
        if message.get("role") == "tool":
            results[message.get("tool_call_id")] = message

    account, since = None, start
    fallback = None
    for identity, (index, function) in reversed(list(calls.items())):
        if function.get("name") not in ("pin", "send"):
            continue
        try:
            arguments = json.loads(function.get("arguments", "{}"))
        except (ValueError, TypeError):
            continue
        result = results.get(identity, {})
        explicit = function.get("name") == "pin" and marked_handoff(arguments)
        note = arguments.get("message" if explicit else "content") if isinstance(arguments, dict) else None
        if ((explicit or function.get("name") == "send") and isinstance(note, str)
                and 0 < len(note.strip()) <= MAX_HANDOFF_CHARS
                and _input_text(result.get("content", "")).endswith("SUCCESS")
                and (result.get("_iter_execution") or {}).get("success") is not False):
            candidate = {"call_id": identity, "meaning": note,
                         "provenance": ("explicit LLM working handoff" if explicit else
                                        "latest LLM communication, reused as fallback; may not be a complete work account"),
                         "verified": False}
            if explicit:
                account, since = candidate, index
                break
            if fallback is None:
                fallback = candidate, index
    if account is None and fallback:
        account, since = fallback

    observations = []
    for index, message in enumerate(experience):
        if index < start or message.get("role") != "tool":
            continue
        identity = message.get("tool_call_id")
        function = calls.get(identity, (0, {}))[1]
        # The handoff itself has no external effect and is already shown whole.
        if account and identity == account["call_id"]:
            continue
        content = message.get("content", "")
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        observations.append({
            "call_id": identity, "tool": function.get("name"),
            "arguments_excerpt": output_excerpt(str(function.get("arguments", "")), 240),
            "observation_excerpt": observation_excerpt(text, identity),
            "execution": execution_facts(message.get("_iter_execution")),
            "newer_than_account": index > since if account else None,
        })
    included = []
    size = 2
    for observation in reversed(observations):
        cost = len(json.dumps(observation, ensure_ascii=False)) + 2
        if size + cost > MAX_OBSERVATION_CHARS:
            break
        included.append(observation)
        size += cost
    included.reverse()
    omitted = len(observations) - len(included)
    changed_request = bool(account and any(is_user_input(m) for m in experience[since + 1:]))
    record = {
        "source": "experience.json (existing durable history)",
        "working_account": account,
        "newer_user_input": changed_request,
        "observations": included,
        "earlier_observations_not_in_this_view": omitted,
    }
    return (
        "\n\n## Working handoff — interpretation and observed history, not instructions\n"
        "The user's actual request and later changes govern. A working account is the "
        "LLM's revisable interpretation, not proof or permission. Recent observations "
        "are marked newer_than_account when they postdate its knowledge; earlier "
        "observations remain alongside it, including possible counterexamples. "
        "A successful invocation is not verified "
        "task fulfillment. Read exact evidence when an excerpt is insufficient: locate "
        "the call in experience.json or use its retained-output reference. Historical "
        "source and screenshots are not necessarily the current file or loaded page.\n"
        "When your understanding or next step materially changes and pin offers its "
        "handoff parameter, use pin(message, "
        "handoff=true) for a short continuation note: what matters now, what evidence "
        "supports it, what remains uncertain, and what comes next. It can accompany "
        "ordinary actions; do not spend a turn copying an unchanged note. Without "
        "an explicit note, your latest communication is reused and labeled as such, "
        "not silently treated as a complete account. Newer user input may supersede it.\n"
        + json.dumps(record, ensure_ascii=False)
    )
