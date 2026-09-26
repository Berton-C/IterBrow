#!/usr/bin/env python3
"""Narrow CLI used by the Electron recovery supervisor."""

import argparse
import json
from pathlib import Path

from iterbrow_runtime.hotload_manager import HotloadManager


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "status", "recover-startup", "supervisor-check", "rollback-probation",
        "attest-candidate",
    ))
    parser.add_argument("--iter-running", choices=("true", "false"), default="false")
    parser.add_argument("--iter-pid", type=int)
    parser.add_argument("--iter-started-at", type=float)
    parser.add_argument("--reason", default="external supervisor requested rollback")
    parser.add_argument("--candidate-id")
    parser.add_argument("--proposal-id")
    args = parser.parse_args()
    manager = HotloadManager(ROOT)
    if args.action == "status":
        result = manager.status()
    elif args.action == "recover-startup":
        result = manager.recover_on_startup()
    elif args.action == "supervisor-check":
        result = manager.supervisor_check(
            args.iter_running == "true",
            iter_pid=args.iter_pid,
            iter_started_at=args.iter_started_at,
        )
    elif args.action == "rollback-probation":
        result = manager.rollback_probation(args.reason)
    else:
        if not args.candidate_id or not args.proposal_id:
            parser.error("attest-candidate requires --candidate-id and --proposal-id")
        result = manager.attest_candidate(args.candidate_id, args.proposal_id)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
