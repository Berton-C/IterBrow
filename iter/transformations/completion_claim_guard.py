"""Question-first review of a previous completion claim, including actual send text.

This is not an outgoing filter or proof checker. The LLM compares the current
request with observations; a phase label never proves fulfillment. All tools,
including communication and recovery, stay available.
"""
import json
import re

DESCRIPTION = "Ask whether completion claims match the actual request and observations; never withhold tools."
TASK_STATE_PATH = "task_state.metta"
_CLAIM_RE = re.compile(
    r"\b(already exists|is now (live|done|complete|built)|has been (built|created|verified)|"
    r"tab \d+ (is|exists)|successfully (built|created|verified)|verified as)\b",
    re.IGNORECASE,
)

def transform(messages, tools):
    try:
        if not isinstance(messages, list):
            return messages, tools
        if any(isinstance(m, dict) and m.get('role') == 'system'
               and '## Completion Claim Guard' in str(m.get('content', '')) for m in messages):
            return messages, tools
        assistant = next((m for m in reversed(messages)
                          if isinstance(m, dict) and m.get('role') == 'assistant'), {})
        texts = [assistant.get('content') or '']
        for call in assistant.get('tool_calls', []):
            if call.get('function', {}).get('name') == 'send':
                try:
                    texts.append(str(json.loads(call['function'].get('arguments', '{}')).get('content', '')))
                except (ValueError, TypeError):
                    pass
        if not any(isinstance(text, str) and _CLAIM_RE.search(text) for text in texts):
            return messages, tools
        note = (
            "\n\n## Completion Claim Guard\n"
            "The previous assistant/send message included a completion claim. For the actual "
            "current request and agreed changes, what observations support it? What was omitted "
            "or remains unverified? A task phase, passing command or another completed task "
            "does not establish fulfillment. Investigate if evidence is missing; correct an "
            "inaccurate claim openly. If already supported, do not repeat checks. "
            "Communication stays available; no phase update is required to speak."
        )
        for message in messages:
            if isinstance(message, dict) and message.get('role') == 'system':
                message['content'] = (message.get('content') or '') + note
                break
    except Exception:
        pass
    return messages, tools
