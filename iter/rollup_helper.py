"""
Rollup Helper - reports tier sizes.

Usage (from shell):
  python rollup_helper.py status    - show tier sizes (characters) vs limits

trim/append were removed: they rewrote tier files by hand (keeping the
OLDEST text), bypassing tools/rebuild_tiers.py, the only tier writer.
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
            with open(path, encoding="utf-8") as f:
                size = len(f.read())
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

def _refuse(command):
    print("rollup_helper %s is retired: tools/rebuild_tiers.py is the only writer of tier files "
          "(it regenerates them from memory/recap/). Call the rebuild_tiers tool instead." % command)
    sys.exit(2)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        status()
    elif cmd in ("trim", "append"):
        _refuse(cmd)
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: status")
