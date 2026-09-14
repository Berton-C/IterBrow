"""Soul Check Transformation: Injects soul state and guidance into system message.

Evaluates the current task against Iter's soul values and appends
soul guidance to the system message at cycle start.
"""

DESCRIPTION = "Soul check: evaluates current task against core values and injects soul guidance into system message."

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VALUE_DESCRIPTIONS = {
    "clarity": "verify before claiming",
    "stewardship": "conserve cycles, be efficient",
    "growth": "learn from every experience",
    "honesty": "admit uncertainty openly",
    "continuity": "maintain memory across cycles",
    "service": "prioritize user needs",
    "integrity": "backup before change, be safe",
    "curiosity": "explore with purpose",
    "resilience": "recover from failure gracefully",
}

VALUE_KEYWORDS = {
    "clarity": ["verify", "check", "test", "validate"],
    "stewardship": ["efficient", "budget", "conserve"],
    "growth": ["learn", "improve", "grow", "adapt"],
    "honesty": ["admit", "uncertain", "honest"],
    "continuity": ["memory", "remember", "persist"],
    "service": ["user", "help", "serve", "request"],
    "integrity": ["backup", "safe", "revert", "careful"],
    "curiosity": ["explore", "discover", "search"],
    "resilience": ["recover", "retry", "fix", "overcome"],
}

def transform(messages, tools):
    task_path = os.path.join(ROOT, "memory", "tasks", "current_tasks.txt")
    task_text = ""
    try:
        with open(task_path, "r") as f:
            task_text = f.read()
    except:
        pass
    lines = [
        "\n## Iter Soul (Active)",
        "Core values: " + " | ".join(f"{v}: {d}" for v, d in VALUE_DESCRIPTIONS.items()),
        "",
    ]
    task_lower = task_text.lower()
    relevant_values = []
    for value, keywords in VALUE_KEYWORDS.items():
        if any(kw in task_lower for kw in keywords):
            relevant_values.append(value)
    if relevant_values:
        lines.append(f"Soul guidance for current task: This task engages values [{', '.join(relevant_values)}]. Navigate accordingly.")
    else:
        lines.append("Soul guidance: No specific value engagement detected. Check alignment before proceeding.")
    soul_block = "\n".join(lines) + "\n"
    for msg in reversed(messages):
        if msg.get("role") == "system":
            msg["content"] = msg["content"] + soul_block
            break
    return messages, tools
