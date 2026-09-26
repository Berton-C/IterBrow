#!/usr/bin/env python3
"""Read-only DIST-1 readiness witness for source installations.

This script observes existing IterBrow product surfaces. It never starts,
stops, repairs, or mutates them, so the installer can use its verdict without
becoming another lifecycle supervisor.
"""

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


READINESS_RANK = {
    "incomplete": 0,
    "installed": 1,
    "runtime_ready": 2,
    "assistant_ready": 3,
}


def _resolved(value):
    if not value:
        return ""
    return str(Path(value).expanduser().resolve())


def _executable_path(value):
    """Make a command path absolute without dereferencing a virtualenv symlink."""
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def _check(name, passed, required, detail):
    return {
        "name": name,
        "passed": bool(passed),
        "required_for": required,
        "detail": detail,
    }


def _assistant_probe_passed(messages, probe_id):
    if not probe_id:
        return False
    marker = "[ITERBROW-INSTALL-PROBE:%s]" % probe_id
    user_index = None
    for index, message in enumerate(messages or []):
        if not isinstance(message, dict):
            continue
        if marker not in str(message.get("content", "")):
            continue
        if message.get("role") == "user" and user_index is None:
            user_index = index
        elif message.get("role") == "iter" and user_index is not None and index > user_index:
            return True
    return False


def assess_readiness(observation):
    """Return a redacted readiness report from already collected observations."""
    checks = []
    installed = observation.get("installed") or {}
    installed_requirements = (
        ("program_files", "required program files"),
        ("lockfiles", "repository-owned dependency locks"),
        ("node_runtime", "Node.js runtime"),
        ("electron_assets", "locked Electron assets"),
        ("python_runtime", "managed Python runtime"),
        ("hyperon_import", "Hyperon native engine import"),
        ("state_manifest", "state ownership manifest"),
    )
    for key, detail in installed_requirements:
        checks.append(_check(key, installed.get(key) is True, "installed", detail))
    installed_ok = all(check["passed"] for check in checks)

    expected_iter_dir = _resolved(observation.get("expected_iter_dir"))
    expected_state_dir = _resolved(Path(expected_iter_dir) / ".runtime" / "atomspace")
    atomspace = observation.get("atomspace") or {}
    atomspace_ok = bool(
        atomspace.get("ready") is True
        and atomspace.get("engine") == "hyperon"
        and atomspace.get("engine_available") is True
        and atomspace.get("epoch")
        and isinstance(atomspace.get("commit"), int)
        and atomspace.get("commit") >= 0
        and atomspace.get("state_hash")
        and _resolved(atomspace.get("iter_dir")) == expected_iter_dir
        and _resolved(atomspace.get("state_dir")) == expected_state_dir
    )
    checks.append(_check(
        "authoritative_atomspace",
        atomspace_ok,
        "runtime_ready",
        "ready Hyperon authority with epoch, commit, hash, and matching state owner",
    ))

    browser = observation.get("browser")
    browser_ok = isinstance(browser, list)
    checks.append(_check(
        "browser_bridge",
        browser_ok,
        "runtime_ready",
        "checkout-scoped bridge answered a read-only getTabs request",
    ))

    active = observation.get("active_generation") or {}
    generation_id = active.get("generation_id")
    generation_ok = bool(active.get("status") == "stable" and generation_id)
    checks.append(_check(
        "stable_generation",
        generation_ok,
        "runtime_ready",
        "active generation is explicitly stable",
    ))

    heartbeat = observation.get("heartbeat") or {}
    now = float(observation.get("now", time.time()))
    max_age = float(observation.get("max_heartbeat_age_s", 120.0))
    heartbeat_at = heartbeat.get("at")
    try:
        heartbeat_age = now - float(heartbeat_at)
    except (TypeError, ValueError):
        heartbeat_age = float("inf")
    heartbeat_ok = bool(
        generation_ok
        and heartbeat.get("generation_id") == generation_id
        and heartbeat.get("hard_floor_ok") is True
        and isinstance(heartbeat.get("pid"), int)
        and heartbeat.get("pid") > 1
        and 0 <= heartbeat_age <= max_age
        and observation.get("heartbeat_process_alive") is True
    )
    checks.append(_check(
        "iter_heartbeat",
        heartbeat_ok,
        "runtime_ready",
        "fresh live heartbeat matches the stable generation and health floor",
    ))

    runtime_ok = installed_ok and atomspace_ok and browser_ok and generation_ok and heartbeat_ok
    probe_id = observation.get("probe_id")
    assistant_ok = runtime_ok and _assistant_probe_passed(
        observation.get("chat_messages") or [], probe_id
    )
    checks.append(_check(
        "durable_chat_round_trip",
        assistant_ok,
        "assistant_ready",
        (
            "labeled user and Iter messages were durably journaled in order"
            if probe_id
            else "no labeled installation probe was requested"
        ),
    ))

    if not installed_ok:
        state = "incomplete"
        next_action = "complete or repair the failed installation checks"
    elif not runtime_ok:
        state = "installed"
        next_action = (
            "open IterBrow if needed, complete provider setup, press Start, "
            "then re-run runtime verification"
        )
    elif not assistant_ok:
        state = "runtime_ready"
        next_action = (
            "complete private provider onboarding and one labeled durable chat round trip"
        )
    else:
        state = "assistant_ready"
        next_action = "none"

    return {
        "schema_version": 1,
        "state": state,
        "checks": checks,
        "next_action": next_action,
    }


def _rpc(socket_path, method, timeout_s):
    request = (json.dumps({"method": method, "params": {}}) + "\n").encode("utf-8")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout_s)
        client.connect(str(socket_path))
        client.sendall(request)
        chunks = []
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            if b"\n" in chunk:
                break
    line = b"".join(chunks).split(b"\n", 1)[0]
    response = json.loads(line.decode("utf-8"))
    if not response.get("ok"):
        raise RuntimeError(response.get("error") or "%s RPC failed" % method)
    return response.get("result")


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _read_chat_messages(path):
    messages = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return messages
    for line in lines:
        if not line:
            continue
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            messages.append(value)
    return messages


def _process_alive(pid):
    try:
        pid = int(pid)
        if pid <= 1:
            return False
        os.kill(pid, 0)
        return True
    except (TypeError, ValueError, OSError):
        return False


def _hyperon_imports(python_bin, timeout_s):
    if not python_bin.is_file() or not os.access(str(python_bin), os.X_OK):
        return False
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run(
            [str(python_bin), "-c", "import hyperon"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def collect_observation(args):
    app_root = Path(args.app_root).expanduser().resolve()
    iter_dir = Path(args.iter_dir).expanduser().resolve()
    python_bin = _executable_path(args.python_bin)
    instance_id = hashlib.sha256(str(app_root).encode("utf-8")).hexdigest()[:16]
    atomspace_socket = Path(
        args.atomspace_socket or "/tmp/iter-metta-%s.sock" % instance_id
    )
    browser_socket = Path(
        args.browser_socket or "/tmp/iter-browser-%s.sock" % instance_id
    )

    program_paths = (
        app_root / "main.js",
        app_root / "package.json",
        iter_dir / "iter.py",
        iter_dir / "metta_server.py",
    )
    lock_paths = (
        app_root / "package-lock.json",
        app_root / "scripts" / "requirements.txt",
    )
    installed = {
        "program_files": all(path.is_file() for path in program_paths),
        "lockfiles": all(path.is_file() for path in lock_paths),
        "node_runtime": shutil.which("node") is not None,
        "electron_assets": (app_root / "node_modules" / "electron" / "package.json").is_file(),
        "python_runtime": python_bin.is_file() and os.access(str(python_bin), os.X_OK),
        "hyperon_import": _hyperon_imports(python_bin, args.timeout),
        "state_manifest": (iter_dir / "state_manifest.json").is_file(),
    }

    try:
        atomspace = _rpc(atomspace_socket, "status", args.timeout)
    except Exception:
        atomspace = None
    try:
        browser = _rpc(browser_socket, "getTabs", args.timeout)
    except Exception:
        browser = None

    active = _read_json(iter_dir / ".runtime" / "hotload" / "active.json")
    heartbeat = _read_json(iter_dir / ".runtime" / "recovery" / "iter_heartbeat.json")
    messages = _read_chat_messages(
        iter_dir / ".runtime" / "electron_ui" / "messages.jsonl"
    )
    return {
        "installed": installed,
        "expected_iter_dir": str(iter_dir),
        "atomspace": atomspace,
        "browser": browser,
        "active_generation": active,
        "heartbeat": heartbeat,
        "heartbeat_process_alive": _process_alive((heartbeat or {}).get("pid")),
        "chat_messages": messages,
        "probe_id": args.probe_id,
        "now": time.time(),
        "max_heartbeat_age_s": args.max_heartbeat_age,
    }


def _human_report(report):
    lines = ["IterBrow readiness: %s" % report["state"]]
    for check in report["checks"]:
        mark = "PASS" if check["passed"] else "WAIT"
        lines.append("  %-4s  %-26s %s" % (mark, check["name"], check["detail"]))
    lines.append("Next: %s" % report["next_action"])
    return "\n".join(lines)


def parse_args(argv=None):
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", default=str(default_root))
    parser.add_argument("--iter-dir", default=str(default_root / "iter"))
    parser.add_argument("--python-bin", default=str(default_root / "iter" / ".venv" / "bin" / "python3"))
    parser.add_argument("--atomspace-socket")
    parser.add_argument("--browser-socket")
    parser.add_argument("--probe-id")
    parser.add_argument("--max-heartbeat-age", type=float, default=120.0)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument(
        "--require",
        choices=("installed", "runtime_ready", "assistant_ready"),
        default="runtime_ready",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    report = assess_readiness(collect_observation(args))
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(_human_report(report))
    return 0 if READINESS_RANK[report["state"]] >= READINESS_RANK[args.require] else 2


if __name__ == "__main__":
    raise SystemExit(main())
