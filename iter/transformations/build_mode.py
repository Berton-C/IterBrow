"""build_mode: the foundry loop in front of the model while an app is being made
(docs/milestones/M14_vault_and_foundry_loop.md D1–D2).

Build mode is on when the last 16 messages hold a new_app/app_probe/app_rollback call, a file-tool call on a
vault/ path, or a person's message with the words build, make me, app or vault. Then BUILD_LOOP is appended
to the system prompt; otherwise nothing. Pure over the message list (no state file); a note for the model,
never a gate: no tool is removed and nothing is refused.
"""
import json
import re

DESCRIPTION = "While an app is being made, puts the research → propose → build → prove → report loop in the prompt."

WINDOW = 16
APP_TOOLS = {"new_app", "app_probe", "app_rollback"}
FILE_TOOLS = {"read_file", "write_file", "edit_file", "list_files", "grep_files"}
WORDS = re.compile(r"\b(?:build|make me|app|vault)\b", re.IGNORECASE)

BUILD_LOOP = """[foundry loop — making or changing an app]
1 Research: beyond a tweak, one websearch(source="github") and at most two github reads for ideas; then stop.
2 Propose: one card(kind="fork") with 2–3 shapes — the ask as stated, the ask plus one creative addition you name, the smallest version — a pattern on each choice; wait for [choice card=… pick=…]. Skip it for a tweak or when the person already said how.
3 Build: new_app, then write_file/edit_file under vault/<id>/; keep probe.json current with each feature.
4 Prove: browser_open_app, browser_wait_for the main element, app_probe(<id>), then one real browser_click on the main action; fix until the probe passes; never report a probe you did not run.
5 Report: one send — what works, what the probe checked, what you would add next — then card(kind="offer") with up to three next steps. When the person says who the app is for, brief it and offer ally_sdk.
Throughout: a message to the person is a question you need answered or a report of a tool result since your last message — never a progress note."""


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


def active(messages):
    for message in [m for m in messages or [] if isinstance(m, dict)][-WINDOW:]:
        role = message.get("role")
        if role == "user" and WORDS.search(_text(message.get("content"))):
            return True
        if role == "assistant":
            for call in message.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                name = (call.get("function") or {}).get("name", "")
                if name in APP_TOOLS:
                    return True
                path = str(_arguments(call).get("path", "")).strip()
                if name in FILE_TOOLS and (path == "vault" or path.startswith("vault/")):
                    return True
    return False


def transform(messages, tools):
    try:
        on = active(messages)
    except Exception:
        return messages, tools
    if not on:
        return messages, tools
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system":
            content = str(message.get("content") or "")
            if BUILD_LOOP not in content:
                message["content"] = content + "\n\n" + BUILD_LOOP
            break
    return messages, tools
