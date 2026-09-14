"""
Rollup Helper â assists with tier overflow summarization.

Usage (from shell):
  python rollup_helper.py status    â show tier sizes vs limits
  python rollup_helper.py trim tier1 5000  â trim tier1 to 5000 chars (keeps beginning)
  python rollup_helper.py append tier4 "new era summary text"  â append to a tier

This is a utility, not a transformation. The agent calls it when
.rollup_needed flag appears in context.
"""
import os, sys

TIER_DIR = "memory/tiers"
TIER_LIMITS = {
    "tier1": 8000, "tier2": 5000, "tier3": 3000,
    "tier4": 1500, "tier5": 300,
}
TIERS_ORDER = ["tier5", "tier4", "tier3", "tier2", "tier1"]

def status():
    print("Tier Status:")
    for tier in TIERS_ORDER:
        path = os.path.join(TIER_DIR, tier + ".txt")
        if os.path.exists(path):
            size = os.stat(path)[6]
            limit = TIER_LIMITS.get(tier, 9999)
            flag = " *** OVER LIMIT ***" if size > limit else ""
            print(f"  {tier}: {size} chars (limit {limit}){flag}")
        else:
            print(f"  {tier}: (not created)")
    flag_path = os.path.join(TIER_DIR, ".rollup_needed")
    if os.path.exists(flag_path):
        print("\nRollup needed:")
        with open(flag_path) as f:
            print(f.read())

def trim(tier, max_chars):
    path = os.path.join(TIER_DIR, tier + ".txt")
    with open(path, "r") as f:
        content = f.read()
    if len(content) <= max_chars:
        print(f"{tier} already {len(content)} chars, no trim needed")
        return
    # Keep beginning, trim from end
    trimmed = content[:max_chars].rsplit("\n", 1)[0] + "\n"
    with open(path, "w") as f:
        f.write(trimmed)
    print(f"Trimmed {tier} from {len(content)} to {len(trimmed)} chars")

def append(tier, text):
    path = os.path.join(TIER_DIR, tier + ".txt")
    mode = "a" if os.path.exists(path) else "w"
    with open(path, mode) as f:
        f.write("\n" + text if os.path.exists(path) else text)
    size = os.stat(path)[6]
    print(f"Appended to {tier}, now {size} chars")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        status()
    elif cmd == "trim":
        trim(sys.argv[2], int(sys.argv[3]))
    elif cmd == "append":
        append(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: status | trim <tier> <max_chars> | append <tier> <text>")
