#!/usr/bin/env python3
"""Agent surface plus a separate Electron-supervisor CLI for app revisions."""

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(os.getenv("ITER_DIR", Path.cwd())).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from iterbrow_runtime.app_revision_manager import AppRevisionManager  # noqa: E402


MANAGER = AppRevisionManager(ROOT)
DESCRIPTION = (
    "Stage, validate and activate registered app revisions with automatic recovery. "
    "Ordinary user-requested work needs no PWQ card. If work explicitly uses PWQ, "
    "supply its proposal_id; its scope and revocation remain binding. "
    "Electron alone supplies load/context evidence and promotion. Actions: "
    "status, stage, validate, propose, activate, rollback."
)


def _json_value(value, label):
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError("%s is required" % label)
    if text.startswith(("{", "[")):
        return json.loads(text)
    candidate = Path(text)
    if candidate.is_file():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(text)


def run(action="status", app_id="crm", candidate_id="", files="", contract="",
        proposal_id="", dispatch_authorization="", required_observations="1",
        observation_timeout="90", reason="agent requested safe app rollback"):
    """Iter-facing operations; external health evidence is intentionally absent."""
    try:
        action = str(action or "status").strip().lower()
        if action == "status":
            result = MANAGER.status(app_id)
        elif action == "stage":
            result = MANAGER.stage(
                app_id,
                _json_value(files, "files"),
                _json_value(contract, "contract"),
            )
        elif action == "validate":
            result = MANAGER.validate(candidate_id)
        elif action == "propose":
            result = MANAGER.propose_candidate(candidate_id, proposal_id or None)
        elif action == "activate":
            result = MANAGER.activate(
                candidate_id, proposal_id, dispatch_authorization,
                required_observations=int(required_observations or 1),
                observation_timeout=float(observation_timeout or 90),
            )
        elif action in ("rollback", "rollback_probation"):
            result = MANAGER.rollback_probation(app_id, reason)
        else:
            raise ValueError("unknown app revision action: %s" % action)
        return json.dumps(result, sort_keys=True, default=str)
    except Exception as exc:
        return json.dumps({"error": "%s: %s" % (type(exc).__name__, exc)})


def _external_guard(parser, supplied):
    if supplied != "electron-main":
        parser.error("external application supervision requires --external-supervisor electron-main")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "status", "list-apps", "recover-startup", "supervisor-check", "supervisor-report",
        "rollback-probation", "attest-candidate",
    ))
    parser.add_argument("--external-supervisor")
    parser.add_argument("--app-id", default="crm")
    parser.add_argument("--candidate-id")
    parser.add_argument("--proposal-id")
    parser.add_argument("--revision-id")
    parser.add_argument("--observation-id")
    parser.add_argument("--renderer-present", choices=("true", "false"), default="true")
    parser.add_argument("--load-ok", choices=("true", "false"), default="false")
    parser.add_argument("--visible-handshake", choices=("true", "false"), default="false")
    parser.add_argument("--context-ok", choices=("true", "false"), default="false")
    parser.add_argument("--context-commit", type=int)
    parser.add_argument("--detail", default="")
    parser.add_argument("--reason", default="external application supervisor requested rollback")
    args = parser.parse_args()
    if args.action == "list-apps":
        result = {"apps": MANAGER.registered_apps()}
    elif args.action == "status":
        result = MANAGER.status(args.app_id)
    elif args.action == "attest-candidate":
        _external_guard(parser, args.external_supervisor)
        if not args.candidate_id or not args.proposal_id:
            parser.error("attest-candidate requires --candidate-id and --proposal-id")
        result = MANAGER.attest_candidate(args.candidate_id, args.proposal_id)
    elif args.action == "recover-startup":
        _external_guard(parser, args.external_supervisor)
        result = MANAGER.recover_on_startup(args.app_id)
    elif args.action == "supervisor-check":
        _external_guard(parser, args.external_supervisor)
        result = MANAGER.supervisor_check(
            args.app_id, renderer_present=args.renderer_present == "true"
        )
    elif args.action == "supervisor-report":
        _external_guard(parser, args.external_supervisor)
        if not args.revision_id or not args.observation_id:
            parser.error("supervisor-report requires --revision-id and --observation-id")
        result = MANAGER.supervisor_report(
            args.app_id, args.revision_id, args.observation_id,
            load_ok=args.load_ok == "true",
            visible_handshake=args.visible_handshake == "true",
            context_ok=args.context_ok == "true",
            context_commit=args.context_commit,
            detail=args.detail,
        )
    else:
        _external_guard(parser, args.external_supervisor)
        result = MANAGER.rollback_probation(args.app_id, args.reason)
    print(json.dumps(result, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
