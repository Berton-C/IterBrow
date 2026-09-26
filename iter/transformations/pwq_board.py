"""Inject the PWQ protocol's board projection into Iter's context.

Approved and in-progress proposals remain visible as authorized work.
The event ledger is authoritative; `.runtime/pwq.json` is a
read-only materialized projection.
"""
import json

PWQ_PATH = ".runtime/pwq.json"
DESCRIPTION = "Inject PWQ board state + user card orders into system message."

def transform(messages, tools):
    try:
        with open(PWQ_PATH) as f:
            board = json.load(f)
        items = board.get("items", [])

        if not items:
            return messages, tools
        orders = [i for i in items if i.get("status") in ("approved", "in_progress") and i.get("dispatch_authorization")]
        active = [i for i in items if i.get("status") not in ("completed", "rejected", "superseded")]
        waiting = [i for i in active if i not in orders]
        ndone = len(items) - len(active)
        lines = ["## PWQ Board (user actions land here next cycle)"]
        if orders:
            lines.append("Authorized PWQ work (%d card(s)); continue in context of the latest user instructions:" % len(orders))
            for i in orders[:4]:
                ui = (i.get("user_input") or "").strip()
                lines.append("- [%s] %s%s [authorization=%s]" % (
                    i.get("status", "?"), i.get("title", i.get("id", "?")),
                    (": " + ui[:100]) if ui else "",
                    i.get("dispatch_authorization"),
                ))
        else:
            lines.append("No open orders on cards.")
        if waiting:
            lines.append("Waiting/paused: " + "; ".join("%s(%s)" % (i.get("id", "?")[:34], i.get("status", "?")) for i in waiting[:6])
                         + (" (+%d more)" % (len(waiting) - 6) if len(waiting) > 6 else ""))
        lines.append("Totals: %d active, %d done." % (len(active), ndone))
        block = "\n".join(lines)

        first_msg = messages[0]
        if isinstance(first_msg, dict):
            content = first_msg.get("content", "")
            if isinstance(content, str):
                first_msg["content"] = content.rstrip() + "\n\n" + block
            elif isinstance(content, list):
                first_msg["content"] = content + [{"type": "text", "text": "\n\n" + block}]
    except Exception:
        pass
    return messages, tools
