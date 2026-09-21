"""
PWQ read path: inject user card actions + board state into the system
message each cycle, so Iter sees the user's PWQ card actions without being
told (closed feedback loop). READ-ONLY on .runtime/pwq.json -- the page's
IPC bridge is the single canonical writer; this transformation never
writes, so the two never race (one_shape_one_writer honored).
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
        orders = [i for i in items if i.get("orders_given") and i.get("status") != "done"]
        active = [i for i in items if i.get("status") != "done"]
        ndone = len(items) - len(active)
        lines = ["## PWQ Board (user actions land here next cycle)"]
        if orders:
            lines.append("USER GAVE ORDERS on %d card(s) - act on these:" % len(orders))
            for i in orders[:4]:
                ui = (i.get("user_input") or "").strip()
                lines.append("- [%s] %s%s" % (i.get("status", "?"), i.get("title", i.get("id", "?")),
                                              (": " + ui[:100]) if ui else ""))
        else:
            lines.append("No open orders on cards.")
        if active:
            lines.append("Waiting: " + "; ".join("%s(%s)" % (i.get("id", "?")[:34], i.get("status", "?")) for i in active[:6])
                         + (" (+%d more)" % (len(active) - 6) if len(active) > 6 else ""))
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
