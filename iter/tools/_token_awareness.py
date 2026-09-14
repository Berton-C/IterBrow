"""
Token Awareness tool -- inspired by OpenUI's session.py token tracking.

Tracks approximate token usage per cycle and surfaces it in context.
Uses character count / 4 as rough token estimate (standard heuristic).
Stores running totals in memory/token_usage.json.

Adapted to Iter: no tiktoken dependency (MicroPython), uses char-based heuristic.
"""
import json
import os

DESCRIPTION = "Track token usage estimates. Args: action (str: 'track'|'report'|'reset'), text (str, optional). Returns JSON with token estimates."

_USAGE_FILE = "memory/token_usage.json"

def _load():
    try:
        with open(_USAGE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"total_tokens": 0, "total_chars": 0, "cycles": 0, "last_estimate": 0}

def _save(data):
    try:
        with open(_USAGE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

def _estimate_tokens(text):
    """Rough token estimate: ~4 chars per token for English text."""
    return max(1, len(text) // 4)

def run(action="report", text=""):
    action = str(action) if action else "report"
    
    if action == "reset":
        data = {"total_tokens": 0, "total_chars": 0, "cycles": 0, "last_estimate": 0}
        _save(data)
        return json.dumps({"status": "reset", "message": "Token tracking cleared."})
    
    if action == "track":
        data = _load()
        est = _estimate_tokens(str(text))
        data["total_tokens"] += est
        data["total_chars"] += len(str(text))
        data["cycles"] += 1
        data["last_estimate"] = est
        _save(data)
        return json.dumps({
            "status": "tracked",
            "estimated_tokens": est,
            "total_tokens": data["total_tokens"],
            "total_chars": data["total_chars"],
            "cycles": data["cycles"]
        })
    
    if action == "report":
        data = _load()
        avg = data["total_tokens"] // max(1, data["cycles"])
        return json.dumps({
            "total_tokens": data["total_tokens"],
            "total_chars": data["total_chars"],
            "cycles": data["cycles"],
            "avg_tokens_per_cycle": avg,
            "last_estimate": data.get("last_estimate", 0),
            "budget_used_pct": round(100 * data["total_tokens"] / 128000, 2)
        })
    
    return json.dumps({"error": f"Unknown action: {action}. Use 'track', 'report', or 'reset'."})
