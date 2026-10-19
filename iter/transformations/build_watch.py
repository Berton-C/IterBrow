"""build_watch: an app changed since its last probe (docs/milestones/M14_vault_and_foundry_loop.md C4).

When Iter's newest turn is a `send` and, since the last real probe of an app in the vault (an `app_probe`
result that ran: "PROBE <app> …"), a write_file/edit_file/new_app result changed vault/<app>/, one line is
added to the system prompt naming the app and the probe to run. A note for the model, never a gate: no
tool is removed, the send is not touched, nothing is stored (it reads only the message list).
"""
import json
import re

DESCRIPTION = "Notes when a vault app changed since its last probe and Iter is reporting; a note, never a gate."

APP = r"([a-z][a-z0-9-]{0,62})"
CHANGED = re.compile(r"\b(?:WROTE|EDITED|NEW-APP) vault/%s[/:]" % APP)
UNCHANGED = re.compile(r"\bWROTE vault/\S+ \(unchanged\)")
PROBED = re.compile(r"\bPROBE %s\b" % APP)
CHANGERS = {"write_file", "edit_file", "new_app"}


def _arguments(call):
    raw = (call.get("function") or {}).get("arguments")
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _text(content):
    if isinstance(content, list):
        return " ".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
    return str(content or "")


def note(messages):
    """The note line(s) for this request, or None."""
    calls = {}
    changed = {}  # app id -> True while a change has no probe after it
    last_assistant = None
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role == "assistant":
            last_assistant = message
            for call in message.get("tool_calls") or []:
                if isinstance(call, dict) and call.get("id"):
                    calls[call["id"]] = ((call.get("function") or {}).get("name", ""), _arguments(call))
        elif role == "tool":
            name, args = calls.get(message.get("tool_call_id"), ("", {}))
            text = _text(message.get("content"))
            if name in CHANGERS:
                found = CHANGED.search(text)
                if found and not UNCHANGED.search(text):
                    changed[found.group(1)] = True
            elif name == "app_probe":
                found = PROBED.search(text)
                if found and found.group(1) == str(args.get("app", found.group(1))).strip():
                    changed[found.group(1)] = False
    if not last_assistant:
        return None
    sending = any(isinstance(c, dict) and (c.get("function") or {}).get("name") == "send"
                  for c in last_assistant.get("tool_calls") or [])
    pending = [app for app, open_change in changed.items() if open_change]
    if not sending or not pending:
        return None
    return "\n".join("[build: vault/%s changed since its last probe — app_probe(%s) before reporting]" % (app, app)
                     for app in pending)


def transform(messages, tools):
    try:
        line = note(messages)
    except Exception:
        return messages, tools
    if not line:
        return messages, tools
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system":
            content = str(message.get("content") or "")
            if line not in content:
                message["content"] = content + "\n\n" + line
            break
    return messages, tools
