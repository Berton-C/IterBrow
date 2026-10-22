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
import re
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
REPORT_TIMEOUT = 60 * 60  # the most Iter gets to report a build (and again for the iteration)
IDLE_TIMEOUT = 15 * 60    # … and the longest silence before the bench moves on


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
        """Iter's replies after `since` (epoch seconds): the sidebar moves outbox files into messages.jsonl
        within a second, so the durable log is read, and the outbox too for anything not yet moved."""
        out = []
        log = self.ui / "messages.jsonl"
        if log.is_file():
            for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("role") == "iter" and float(row.get("at") or 0) / 1000 >= since:
                    out.append(str(row.get("content", "")))
        for path in sorted((self.ui / "outbox").glob("*.json")) if (self.ui / "outbox").is_dir() else []:
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
                if float(row.get("at") or 0) / 1000 >= since:
                    out.append(str(row.get("content", "")))
            except (OSError, ValueError):
                continue
        return out

    def wait_report(self, app_id, since, timeout=REPORT_TIMEOUT, idle=IDLE_TIMEOUT, since_count=None):
        """The report, or None. A report is a passing app_probe of the app in Iter's record followed by a reply
        (the reply text is returned); gives up after `idle` seconds with no new reply at all, or `timeout`
        seconds in total, so a build in progress is never superseded by the next ask."""
        started = time.time()
        last_activity = started
        seen = 0
        self.last_reason = None
        failing_since = None
        while time.time() < started + timeout:
            phase = self.heartbeat_phase()
            if phase == "request_blocked":  # M15-A4: a blocked Iter ends the app now, not after the silence
                self.last_reason = "request_blocked"
                return None
            # M15-A5: a provider refusing for three minutes straight ends the app with the reason, not after 15 idle
            # minutes that look like a slow build (2026-10-22: 840 silent retries during kanban).
            if phase in ("provider_retry", "error"):
                failing_since = failing_since or time.time()
                if time.time() - failing_since > 180:
                    self.last_reason = phase
                    return None
            else:
                failing_since = None
            replies = self.replies_since(since)
            if len(replies) > seen:
                seen, last_activity = len(replies), time.time()
            if self.probe_passed_then_reported(since_count, app_id):
                return replies[-1] if replies else "(reported)"
            if time.time() - last_activity > idle:
                return None
            time.sleep(5)
        return None

    def heartbeat_phase(self):
        try:
            return json.loads((self.root / ".runtime" / "recovery" / "iter_heartbeat.json").read_text(encoding="utf-8")).get("phase")
        except (OSError, ValueError, AttributeError):
            return None

    def preflight(self):
        """Why the bench must not start, or None: Iter not running (its heartbeat is stale), asks already
        waiting in the inbox (they would arrive as one batch), or an app folder already present."""
        heartbeat = self.root / ".runtime" / "recovery" / "iter_heartbeat.json"
        try:
            beat = json.loads(heartbeat.read_text(encoding="utf-8"))
            age = time.time() - float(beat.get("at") or 0)
        except (OSError, ValueError):
            return "Iter has no heartbeat; press Start in IterBrow first"
        if age > 120:
            return "Iter's last heartbeat was %d s ago; press Start in IterBrow first" % age
        if beat.get("phase") == "request_blocked":  # M15-A4 (2026-10-21: 75 minutes against a blocked Iter)
            return "Iter is blocked and cannot send a request: %s" % str(beat.get("detail", ""))[:300]
        waiting = [p.name for p in (self.ui / "inbox").glob("*")] if (self.ui / "inbox").is_dir() else []
        if waiting:
            return "%d message(s) already waiting in the inbox; let Iter take them (or clear the inbox) first" % len(waiting)
        try:
            vault = json.loads((self.root / ".runtime" / "settings.json").read_text(encoding="utf-8")).get("vault")
        except (OSError, ValueError):
            vault = None
        if not vault:
            return "no apps folder chosen (Apps ▸ Choose apps folder…)"
        present = [b["id"] for b in json.loads((HERE / "briefs.json").read_text(encoding="utf-8")) if (Path(vault) / b["id"]).exists()]
        if present:
            return "already in the apps folder: %s — delete them for a fresh run" % ", ".join(present)
        return None

    def probe_passed_then_reported(self, since_count, app_id):
        """True once Iter's own record shows a passing app_probe of `app_id` followed by a reply — the report
        is evidence, not words (a progress note that mentions the probe is not a report)."""
        names = {}
        passed_at = None
        for index, message in enumerate(self.experience_since(since_count)):
            if message.get("role") == "assistant":
                for call in message.get("tool_calls") or []:
                    names[call.get("id")] = (call.get("function") or {}).get("name", "")
                if passed_at is not None and any((c.get("function") or {}).get("name") == "send" for c in message.get("tool_calls") or []):
                    return True
            elif message.get("role") == "tool" and names.get(message.get("tool_call_id")) not in ("send", None):
                # M15-F2: the probe may run through the python tool (app_probe(app=…) as a function); the result
                # text is the evidence, whichever tool returned it (words in a send never count).
                text = str(message.get("content", ""))
                if re.search(r"PROBE %s\b[^\n]*: \d+ passed, 0 failed" % re.escape(app_id), text):
                    passed_at = index
        return False

    def experience_since(self, mark):
        """The loop's messages added after `mark` (from experience_mark()). The loop rotates experience.json,
        so position is useless: a message is new when its tool-call ids were not there at the mark."""
        try:
            data = json.loads((self.root / "experience.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        seen = set(mark or [])
        out = []
        for message in data:
            ids = self._ids(message)
            if ids and ids <= seen:
                continue
            if not ids and not out:
                continue  # a user line before the first new turn is the ask itself or older
            out.append(message)
        return out

    @staticmethod
    def _ids(message):
        if message.get("role") == "assistant":
            return {c.get("id") for c in message.get("tool_calls") or [] if isinstance(c, dict) and c.get("id")}
        if message.get("role") == "tool" and message.get("tool_call_id"):
            return {message["tool_call_id"]}
        return set()

    def experience_mark(self):
        """Every tool-call id in experience.json now (see experience_since)."""
        try:
            data = json.loads((self.root / "experience.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return set()
        ids = set()
        for message in data if isinstance(data, list) else []:
            ids |= self._ids(message)
        return ids

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
    start, before = time.time(), it.experience_mark()
    it.say(brief["ask"])
    report = it.wait_report(brief["id"], start, since_count=before)
    record["elapsed_s"] = round(time.time() - start, 1)
    record["reported"] = report is not None
    if getattr(it, "last_reason", None):
        record["reason"] = it.last_reason
    record.update(count_loop(it.experience_since(before)))
    record["sends_before_report"] = max(0, record.pop("sends") - (1 if report else 0))
    try:
        record["probe_passed"], record["probe"] = it.probe(brief)
    except Exception as error:  # the app is missing, never loaded, or the bridge refused
        record["probe_passed"], record["probe"] = False, {"error": str(error)}
    record["iteration_kept_working"] = None
    if iterate and record["reported"]:
        since, before_iteration = time.time(), it.experience_mark()
        it.say(brief["iterate"])
        record["iteration_reported"] = it.wait_report(brief["id"], since, since_count=before_iteration) is not None
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
    problem = it.preflight()
    if problem:
        print("[bench] not starting: " + problem)
        return 2
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
