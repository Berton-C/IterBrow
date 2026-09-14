import json
import os



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

DESCRIPTION = "Query NAL truth-weighted tool reliability scores. Returns (f, c, calls) for all tracked tools."

RELIABILITY_FILE = "transformations/.runtime/tool_reliability.json"

def nal_revise(f1, c1, f2, c2):
    w1 = c1 / (1 - c1) if c1 < 1.0 else 1e10
    w2 = c2 / (1 - c2) if c2 < 1.0 else 1e10
    f_new = (w1 * f1 + w2 * f2) / (w1 + w2)
    c_new = (w1 + w2) / (w1 + w2 + 1)
    return round(f_new, 4), round(c_new, 4)

def run():
    if not _exists(RELIABILITY_FILE):
        return "No reliability data yet."

    try:
        with open(RELIABILITY_FILE, 'r') as f:
            scores = json.loads(f.read())
    except (ValueError, IOError):
        return "Reliability file corrupted or empty."

    lines = ["=== NAL Tool Reliability ==="]
    lines.append(f"{'Tool':<20} {'f':<8} {'c':<8} {'calls':<8} {'succ':<8} {'fail':<8}")
    lines.append("-" * 60)

    for tool_name in sorted(scores.keys()):
        s = scores[tool_name]
        succ = s.get('successes', 0)
        fail = s.get('failures', 0)
        lines.append(f"{tool_name:<20} {s['f']:<8.4f} {s['c']:<8.4f} {s['calls']:<8} {succ:<8} {fail:<8}")

    return "\n".join(lines)
