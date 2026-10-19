#!/usr/bin/env python3
"""The five-app foundry benchmark (docs/milestones/M14_vault_and_foundry_loop.md G2; how to run: docs/bench/README.md).

Against a running IterBrow (you start it, choose an apps folder and start Iter): for each brief in
briefs.json it writes the ask into the chat inbox as the sidebar does, waits (at most 20 minutes) for Iter's
report, opens the app over the bridge, clears the app's own storage (iter:<id>: keys only), runs the brief's
probe on the real page, and counts what the loop did. A second phase sends the brief's iteration ask and
probes again: does the app still work after a change? Results go to docs/bench/<date>-<model>.json and a
table on stdout.

    ITER_DIR=~/…/IterBrow/iter python3 scripts/foundry_bench/bench.py [--app todo] [--baseline] [--model NAME]

score(record) and table(records) are pure (tests/test_m14_bench.py).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import socket
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REPORT_TIMEOUT = 20 * 60  # seconds Iter gets to report a build (and again for the iteration)


# ---- pure ------------------------------------------------------------------------------------------------
def score(record):
    """built: the brief's probe passed on the first try; kept: it still passed after the iteration (None when
    the iteration was not run); theatre: messages that reported no tool result since the previous one."""
    kept = record.get("iteration_kept_working")
    return {"built": bool(record.get("probe_passed")), "kept": None if kept is None else bool(kept),
            "theatre": int(record.get("sends_without_tool_result") or 0)}


def _yes(value):
    return "-" if value is None else ("yes" if value else "no")


def table(records):
    """A plain-text table, one row per record."""
    header = ["app", "model", "built", "kept", "theatre", "cycles", "tools", "cards", "minutes"]
    rows = [header]
    for record in records:
        s = score(record)
        rows.append([record.get("app", "?"), record.get("model", "?") + (" (baseline)" if record.get("baseline") else ""),
                     _yes(s["built"]), _yes(s["kept"]), str(s["theatre"]), str(record.get("cycles", 0)),
                     str(record.get("tool_calls", 0)), str(record.get("cards", 0)),
                     "%.1f" % (float(record.get("elapsed_s") or 0) / 60)])
    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    return "\n".join("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip() for row in rows)


def count_loop(messages):
    """Counts over the assistant/tool messages of one run (experience.json entries after the ask). A send
    with no other tool result since the previous message counts as theatre (a question counts too: the
    briefs need none)."""
    cycles = tool_calls = cards = sends = theatre = 0
    names = {}
    results_since_send = 0
    for message in messages:
        if message.get("role") == "assistant":
            cycles += 1
            for call in message.get("tool_calls") or []:
                name = (call.get("function") or {}).get("name", "")
                names[call.get("id")] = name
                if name == "send":
                    sends += 1
                    if results_since_send == 0:
                        theatre += 1
                    results_since_send = 0
                elif name != "nop":
                    tool_calls += 1
                    if name == "card":
                        cards += 1
        elif message.get("role") == "tool" and names.get(message.get("tool_call_id")) not in ("send", "nop", None):
            results_since_send += 1
    return {"cycles": cycles, "tool_calls": tool_calls, "cards": cards, "sends": sends,
            "sends_without_tool_result": theatre}


# ---- talking to IterBrow ---------------------------------------------------------------------------------
class Iter:
    def __init__(self, iter_dir, socket_path=None):
        self.root = Path(iter_dir).expanduser().resolve()
        self.ui = self.root / ".runtime" / "electron_ui"
        repo = self.root.parent
        default = "/tmp/iter-browser-%s.sock" % hashlib.sha256(str(repo).encode()).hexdigest()[:16]
        self.socket = socket_path or os.environ.get("ITER_BRIDGE_SOCKET") or default

    def say(self, text):
        inbox = self.ui / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        staging = self.ui / (".bench-%d.tmp" % time.time_ns())
        staging.write_text(text, encoding="utf-8")
        os.replace(staging, inbox / ("%d-bench.txt" % time.time_ns()))

    def replies_since(self, since):
        out = []
        for path in sorted((self.ui / "outbox").glob("*.json")) if (self.ui / "outbox").is_dir() else []:
            if path.stat().st_mtime < since:
                continue
            try:
                out.append(str(json.loads(path.read_text(encoding="utf-8")).get("content", "")))
            except (OSError, ValueError):
                continue
        return out

    def wait_report(self, app_id, since, timeout=REPORT_TIMEOUT):
        """The first reply after `since` that names the app and says what the probe found, or None."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            for reply in self.replies_since(since):
                lower = reply.lower()
                if app_id in lower and ("probe" in lower or "works" in lower or "built" in lower):
                    return reply
            time.sleep(5)
        return None

    def experience_since(self, since_count):
        try:
            data = json.loads((self.root / "experience.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return data[since_count:] if isinstance(data, list) else []

    def experience_count(self):
        return len(self.experience_since(0))

    def bridge(self, method, timeout=40, **params):
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(timeout)
        try:
            connection.connect(self.socket)
            connection.sendall((json.dumps({"method": method, "params": params}) + "\n").encode("utf-8"))
            data = b""
            while b"\n" not in data:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                data += chunk
        finally:
            connection.close()
        reply = json.loads(data.decode("utf-8").split("\n")[0] or "{}")
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error", "bridge call failed"))
        return reply.get("result")

    def probe(self, brief):
        """Open the app, clear only its own iter:<id>: storage, reload, run the brief's probe."""
        app_id = brief["id"]
        opened = self.bridge("openApp", appId=app_id)
        tab = opened.get("tabId")
        prefix = json.dumps("iter:%s:" % app_id)
        self.bridge("eval", tabId=tab, expression="(() => { const p = %s; Object.keys(localStorage).filter((k) => "
                    "k.startsWith(p)).forEach((k) => localStorage.removeItem(k)); location.reload(); return true; })()" % prefix)
        time.sleep(1.5)
        self.bridge("waitFor", tabId=tab, selector=brief["main_action"], timeoutMs=15000)
        result = self.bridge("probe", appId=app_id, steps=brief["probe"]["steps"],
                             assertions=brief["probe"]["assertions"], timeoutMs=8000)
        return result.get("failed", 1) == 0 and result.get("passed", 0) == len(brief["probe"]["assertions"]), result


def model_name(iter_dir):
    try:
        settings = json.loads((Path(iter_dir) / ".runtime" / "settings.json").read_text(encoding="utf-8"))
        provider = settings.get("provider", "?")
        return "%s:%s" % (provider, (settings.get(provider) or {}).get("model", "?"))
    except (OSError, ValueError):
        return "unknown"


def run_brief(it, brief, model, baseline, iterate=True):
    record = {"app": brief["id"], "model": model, "baseline": baseline, "at": dt.datetime.now().isoformat(timespec="seconds")}
    start, before = time.time(), it.experience_count()
    it.say(brief["ask"])
    report = it.wait_report(brief["id"], start)
    record["elapsed_s"] = round(time.time() - start, 1)
    record["reported"] = report is not None
    record.update(count_loop(it.experience_since(before)))
    record["sends_before_report"] = max(0, record.pop("sends") - (1 if report else 0))
    try:
        record["probe_passed"], record["probe"] = it.probe(brief)
    except Exception as error:  # the app is missing, never loaded, or the bridge refused
        record["probe_passed"], record["probe"] = False, {"error": str(error)}
    record["iteration_kept_working"] = None
    if iterate and record["reported"]:
        since = time.time()
        it.say(brief["iterate"])
        record["iteration_reported"] = it.wait_report(brief["id"], since) is not None
        try:
            record["iteration_kept_working"], record["iteration_probe"] = it.probe(brief)
        except Exception as error:
            record["iteration_kept_working"], record["iteration_probe"] = False, {"error": str(error)}
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description="The five-app foundry benchmark (docs/bench/README.md).")
    parser.add_argument("--app", help="run one brief (todo, pomodoro, notes, convert, kanban)")
    parser.add_argument("--baseline", action="store_true", help="tag the record as a baseline (before a change)")
    parser.add_argument("--model", help="label for the model (default: from .runtime/settings.json)")
    parser.add_argument("--no-iterate", action="store_true", help="skip the iteration phase")
    parser.add_argument("--socket", help="bridge socket (default: ITER_BRIDGE_SOCKET or IterBrow's own)")
    args = parser.parse_args(argv)
    iter_dir = os.environ.get("ITER_DIR")
    if not iter_dir:
        parser.error("set ITER_DIR to your IterBrow's iter/ folder")
    briefs = json.loads((HERE / "briefs.json").read_text(encoding="utf-8"))
    if args.app:
        briefs = [b for b in briefs if b["id"] == args.app]
        if not briefs:
            parser.error("no brief named %s" % args.app)
    it = Iter(iter_dir, args.socket)
    model = args.model or model_name(iter_dir)
    records = []
    for brief in briefs:
        print("[bench] %s …" % brief["id"], flush=True)
        records.append(run_brief(it, brief, model, args.baseline, iterate=not args.no_iterate))
        print(table(records[-1:]).splitlines()[-1], flush=True)
    out = REPO / "docs/bench/" / ("%s-%s%s.json" % (dt.date.today().isoformat(), model.replace("/", "_").replace(":", "_"),
                                                    "-baseline" if args.baseline else ""))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print("\n" + table(records) + "\n\nwritten: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
