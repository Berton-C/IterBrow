#!/usr/bin/env python3
"""JSON stdin/stdout process boundary for the canonical PWQ writer."""

import json
import os
import sys
from pathlib import Path

from iterbrow_runtime.pwq_protocol import PWQStore


ROOT = Path(os.environ.get("ITER_DIR") or Path(__file__).resolve().parent).resolve()
STORE = PWQStore(ROOT / ".runtime" / "pwq", ROOT / ".runtime" / "pwq.json")


def main():
    request = json.load(sys.stdin)
    action = request.get("action", "read")
    if action == "read":
        if not STORE.events_path.exists() and not STORE.projection_path.exists():
            seed_path = ROOT / "pwq_seed.json"
            if seed_path.exists():
                result = STORE.sync_board(json.loads(seed_path.read_text(encoding="utf-8")), actor="seed")
            else:
                result = STORE.read()
        else:
            result = STORE.read()
    elif action == "sync":
        result = STORE.sync_board(request.get("board"), actor=request.get("actor", "human"))
    else:
        result = STORE.command(
            action,
            request.get("proposal_id"),
            actor=request.get("actor", "iter"),
            payload=request.get("payload") or {},
            expected_version=request.get("expected_version"),
            command_id=request.get("command_id"),
        )
    json.dump({"ok": True, "result": result}, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        json.dump({"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}, sys.stdout)
        sys.stdout.write("\n")
        sys.exit(2)
