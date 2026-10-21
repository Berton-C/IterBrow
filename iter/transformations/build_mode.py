"""build_mode: the foundry loop in front of the model while an app is being made
(docs/milestones/M14_vault_and_foundry_loop.md D1–D2).

Build mode is on when the last 16 messages hold a new_app/app_probe/app_rollback call, a file-tool call on a
vault/ path, or a person's message with the words build, make me, app or vault. Then BUILD_LOOP is appended
to the system prompt; otherwise nothing. Pure over the message list (no state file); a note for the model,
never a gate: no tool is removed and nothing is refused.
"""
import json
import os
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
4 Prove: after each edit browser_open_app (reloads a changed app), browser_wait_for the main element, app_probe(<id>), one real browser_click on the main action; fix until the probe passes; never report a probe you did not run.
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


APP_ARG = {"new_app": "id", "app_probe": "app", "app_rollback": "app", "browser_open_app": "app_id"}
VAULT_PATH = re.compile(r"^vault/([a-z][a-z0-9-]{0,62})(?:/|$)")
REPORTED = "transformations/.runtime/build_ledger_reported"  # M15-C6: the last send learned from


def current_app(messages):
    """The app the newest app-tool call or vault file-tool call names in the window, or None."""
    for message in reversed([m for m in messages or [] if isinstance(m, dict)][-WINDOW:]):
        for call in reversed(message.get("tool_calls") or [] if message.get("role") == "assistant" else []):
            if not isinstance(call, dict):
                continue
            name = (call.get("function") or {}).get("name", "")
            args = _arguments(call)
            if name in APP_ARG and re.match(r"^[a-z][a-z0-9-]{0,62}$", str(args.get(APP_ARG[name], "")).strip()):
                return str(args[APP_ARG[name]]).strip()
            found = VAULT_PATH.match(str(args.get("path", "")).strip()) if name in FILE_TOOLS else None
            if found:
                return found.group(1)
    return None


def ask_text(messages, app):
    """What the person asked for this app (M15-C2, read literally): their messages that name it — anywhere in
    the history handed to transformations, since the ask scrolls out of the 16-message window within a few
    cycles — and the one the build answers (the last before the first call that touched it)."""
    named = re.compile(r"\b%s\b" % re.escape(app))
    texts, last_user = [], None
    touched = False
    for message in [m for m in messages or [] if isinstance(m, dict)]:
        if message.get("role") == "user" and not message.get("_iter_runner"):
            text = _text(message.get("content"))
            last_user = text
            if named.search(text):
                texts.append(text)
        elif message.get("role") == "assistant" and not touched and current_app([message]) == app:
            touched = True
            if last_user and last_user not in texts:
                texts.append(last_user)
    return "\n".join(texts)


def _newest_write_ms(folder):
    newest = 0.0
    for base, dirs, files in os.walk(str(folder)):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        for name in files:
            try:
                newest = max(newest, os.stat(os.path.join(base, name)).st_mtime)
            except OSError:
                pass
    return newest * 1000


def _learn_from_send(messages, app, atoms, ledger):
    """M15-C6: the newest assistant turn sent a message while building — a report; NACE hears whether the
    ledger said report. Once per send (its call id is kept)."""
    newest = next((m for m in reversed(messages or []) if isinstance(m, dict) and m.get("role") == "assistant"), None)
    sends = [c for c in (newest or {}).get("tool_calls") or [] if isinstance(c, dict) and (c.get("function") or {}).get("name") == "send"]
    if not sends:
        return
    ident = str(sends[-1].get("id") or "")
    try:
        if ident and open(REPORTED).read().strip() == ident:
            return
    except OSError:
        pass
    if ledger.learn_from_report(app, atoms) is not None:
        try:
            os.makedirs(os.path.dirname(REPORTED), exist_ok=True)
            with open(REPORTED, "w") as handle:
                handle.write(ident)
        except OSError:
            pass


def ledger_note(messages):
    """M15-C4: the stored build ledger line for the app being built (atoms read, no MeTTa per cycle), or
    "[build ledger <app>: stale — re-check]" when its files changed since the last check. Also records what
    the ask names (facts_from_ask) when it grew. None when there is no app or the store cannot be read."""
    app = current_app(messages)
    if not app:
        return None
    from iterbrow_runtime import build_ledger, vault
    folder = vault.app_dir(app)
    if folder is None:
        return None
    atoms = build_ledger.read(app)
    text = ask_text(messages, app)
    if text:
        try:
            build_ledger.record_ask(app, text, atoms)
        except Exception as error:
            print("[build ledger] ask facts not recorded: %s" % error)
    _learn_from_send(messages, app, atoms, build_ledger)
    line, checked = build_ledger.stored_line(app, atoms)
    if line is None or (checked or 0) < _newest_write_ms(folder):
        return "[build ledger %s: stale — re-check with browser_open_app(%s)]" % (app, app)
    return line


THEATRE = ("[you sent two messages in a row with nothing done between them — do the next step (a tool call), "
           "then say what it showed]")


def theatre(messages):
    """M14-H3: the newest assistant turn is a send, and so was the previous one, with no other tool result
    between them (a progress note after a progress note). None otherwise. Pure; a note, never a gate."""
    turns = []
    names = {}
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        if message.get("role") == "assistant":
            calls = [c for c in message.get("tool_calls") or [] if isinstance(c, dict)]
            for call in calls:
                names[call.get("id")] = (call.get("function") or {}).get("name", "")
            kinds = {(c.get("function") or {}).get("name", "") for c in calls}
            turns.append("send" if kinds == {"send"} else ("other" if kinds else "text"))
        elif message.get("role") == "tool" and names.get(message.get("tool_call_id")) not in ("send", "nop", None):
            turns.append("result")
        elif message.get("role") == "user":
            turns.append("user")
    recent = [t for t in turns if t != "text"]
    return THEATRE if len(recent) >= 2 and recent[-1] == "send" and recent[-2] == "send" else None


def transform(messages, tools):
    try:
        on = active(messages)
        note = theatre(messages) if on else None
    except Exception:
        return messages, tools
    if not on:
        return messages, tools
    try:
        ledger = ledger_note(messages)  # M15-C4: the build ledger, never a gate
    except Exception as error:
        print("[build ledger] unavailable: %s" % error)
        ledger = None
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system":
            content = str(message.get("content") or "")
            if BUILD_LOOP not in content:
                content += "\n\n" + BUILD_LOOP
            if note and note not in content:
                content += "\n\n" + note
            if ledger:
                content += "\n\n" + ledger
            message["content"] = content
            break
    return messages, tools
