"""M15-C: the build ledger — facts observed about an app being built, conclusions derived by MeTTa rules
(seeds/build_ledger.metta) when the facts change, and a short rendered line the model reads.

Spec: docs/milestones/M15_build_ledger.md section C.

- Facts come from what the ask literally names (`facts_from_ask`) and from what the running app shows: the
  contract check run in its page (`facts_from_check`) and probes (`facts_from_probe`). Nothing is parsed out
  of source files.
- `observe(...)` replaces the app's observed families wholesale, derives the conclusions over the app's
  facts through the one-shot Hyperon worker (the evaluator the service uses for every query), and stores
  facts and conclusions in one transaction. The rendered line comes from the observation in hand, so it
  reaches the model even when the store write failed (it then ends "(not recorded)").
- `build_mode` reads the stored line each cycle (`stored_line`); no MeTTa runs per cycle.

Atoms are keyed `state:build:<app>:<family>:<n>`. Callers catch every ledger failure: it never fails a tool.
Never a gate: the ledger says what is open; nothing is refused.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ITER_DIR = Path(__file__).resolve().parents[1]
SEED = ITER_DIR / "seeds" / "build_ledger.metta"
APP_ID = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
# `#id` / `.class` tokens the person wrote: a letter after the mark and nothing word-like before it, so
# 3.28, e.g. and example.com are not selectors.
SELECTOR = re.compile(r"(?<![\w#.\-/:])([#.][A-Za-z_][\w-]*)")
PERSIST = re.compile(r"\b(?:persist\w*|reload\w*|remember\w*)\b", re.IGNORECASE)
PROBE_RUNS_KEPT = 3  # the newest runs a probe observation keeps (regressions need an earlier run)
WORKER_TIMEOUT = 45


def _q(text):
    """A MeTTa string literal."""
    return '"%s"' % str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _unq(text):
    return text.replace('\\"', '"').replace("\\\\", "\\")


def _prefix(app, family=""):
    return "state:build:%s:%s" % (app, (family + ":") if family else "")


def _numbered(app, family, atoms):
    return [("%s%d" % (_prefix(app, family), index), atom) for index, atom in enumerate(atoms)]


# ---------------------------------------------------------------- facts (pure)

def selectors_in(text):
    seen = []
    for token in SELECTOR.findall(str(text or "")):
        if token not in seen:
            seen.append(token)
    return seen


def facts_from_ask(app, text):
    """M15-C2: `(ask-requires app "<selector>")` for every #id/.class the ask names and `(ask-requires app
    persist)` when it says persist/reload/remember — nothing else, ever (precision over recall)."""
    atoms = ["(ask-requires %s %s)" % (app, _q(sel)) for sel in selectors_in(text)]
    if PERSIST.search(str(text or "")):
        atoms.append("(ask-requires %s persist)" % app)
    return _numbered(app, "ask", atoms)


def facts_from_check(app, check):
    """M15-C2: the contract check (page_scripts.checkScript) as atoms."""
    atoms = []
    check = check or {}
    for sel, state in (check.get("selectors") or {}).items():
        if (state or {}).get("present"):
            atoms.append("(app-has %s %s)" % (app, _q(sel)))
            if state.get("visible"):
                atoms.append("(app-visible %s %s)" % (app, _q(sel)))
    if "ready" in check:
        atoms.append("(app-ready %s %s)" % (app, "true" if check.get("ready") else "false"))
    storage = check.get("storage") or {}
    if int(storage.get("prefixed") or 0) > 0:
        atoms.append("(app-stores %s prefixed)" % app)
    if storage.get("other"):
        atoms.append("(app-stores %s other)" % app)
    for host in check.get("scripts") or []:
        atoms.append("(app-script %s external %s)" % (app, _q(host)))
    for form in check.get("forms") or []:
        atoms.append("(app-form %s %s %s)" % (app, _q(form.get("selector")), "guarded" if form.get("guarded") else "unguarded"))
    if "placeholder" in check:
        atoms.append("(app-placeholder %s %s)" % (app, "present" if check.get("placeholder") else "gone"))
    return _numbered(app, "check", atoms)


def _shown(value):
    if value is None:
        return "nothing"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def facts_from_probe(app, result, probe_json, seq):
    """M15-C2: one probe run — `(probe-run app seq passed failed)`, each assertion, and every selector a step
    or assertion of the probe touches (`probe-covers`)."""
    result = result or {}
    atoms = ["(probe-run %s %d %d %d)" % (app, seq, int(result.get("passed") or 0), int(result.get("failed") or 0))]
    for item in result.get("observations") or []:
        label = _q("%s %s" % (item.get("kind"), item.get("selector")))
        if item.get("passed"):
            atoms.append('(probe-assertion %s %d %s passed "")' % (app, seq, label))
        else:
            detail = "%s≠%s" % (_shown(item.get("actual")), _shown(item.get("expected")))
            atoms.append("(probe-assertion %s %d %s failed %s)" % (app, seq, label, _q(detail[:120])))
    covered = []
    probe_json = probe_json or {}
    for item in list(probe_json.get("steps") or []) + list(probe_json.get("assertions") or []):
        for sel in selectors_in((item or {}).get("selector", "")):
            if sel not in covered:
                covered.append(sel)
    atoms.extend("(probe-covers %s %d %s)" % (app, seq, _q(sel)) for sel in covered)
    return [("%s%d:%d" % (_prefix(app, "probe"), seq, index), atom) for index, atom in enumerate(atoms)]


# ---------------------------------------------------------------- conclusions (MeTTa)

QUERIES = ("missing", "hidden", "unproven", "regressed", "contract", "probe", "failure", "passing-run")


def _tokens(text):
    """Tokens of Hyperon's printed results: brackets and parens, strings (unescaped), bare words."""
    out, i = [], 0
    while i < len(text):
        char = text[i]
        if char in "[]()":
            out.append(char)
            i += 1
        elif char == '"':
            j, buf = i + 1, []
            while j < len(text) and text[j] != '"':
                if text[j] == "\\" and j + 1 < len(text):
                    j += 1
                buf.append(text[j])
                j += 1
            out.append(("str", "".join(buf)))
            i = j + 1
        elif char in " ,\n\t":
            i += 1
        else:
            j = i
            while j < len(text) and text[j] not in '[](), \n\t"':
                j += 1
            out.append(text[i:j])
            i = j
    return out


def _parse(text):
    tokens = _tokens(text)
    position = 0

    def node():
        nonlocal position
        token = tokens[position]
        position += 1
        if token in ("[", "("):
            close = "]" if token == "[" else ")"
            items = []
            while tokens[position] != close:
                items.append(node())
            position += 1
            return items
        return token

    return node()


def _plain(item):
    """A parsed atom as text: a string's value, a word as is, an expression as `head "arg"`."""
    if isinstance(item, tuple):
        return item[1]
    if isinstance(item, list):
        return " ".join(('"%s"' % part[1]) if isinstance(part, tuple) else _plain(part) for part in item)
    return str(item)


def conclude(app, run):
    """M15-C3: the rules' conclusions for `app`. `run(code)` evaluates the `!` lines over the app's facts and
    returns Hyperon's printed results (the one-shot worker, or a test's run_metta)."""
    code = "\n".join("!(collapse (ledger-%s %s))" % (name, app) for name in QUERIES) + "\n!(ledger-next %s)" % app
    parsed = _parse(run(code))
    rows = [row[0] if isinstance(row, list) and row else row for row in parsed]
    values = dict(zip(QUERIES + ("next",), rows))

    def names(key):
        found = values.get(key)
        return sorted({_plain(item) for item in found}) if isinstance(found, list) else []

    probe = None
    runs = values.get("probe") if isinstance(values.get("probe"), list) else []
    if runs and isinstance(runs[0], list) and len(runs[0]) == 3:
        failures = sorted("%s: %s" % (_plain(item[1]), _plain(item[2])) for item in values.get("failure") or []
                          if isinstance(item, list) and len(item) == 3)
        probe = {"passed": int(runs[0][1]), "failed": int(runs[0][2]), "failures": failures}
    nxt = values.get("next")
    return {"missing": names("missing"), "hidden": names("hidden"), "unproven": names("unproven"),
            "regressed": names("regressed"), "contract": names("contract"), "probe": probe,
            "proven": bool(values.get("passing-run")),
            "next": nxt if nxt in ("build", "probe", "report") else "build"}


CONTRACT_WORDS = {"ready": "ready flag not set", "storage": "storage other", "placeholder": "placeholder still there"}


def _contract(item):
    if item in CONTRACT_WORDS:
        return CONTRACT_WORDS[item]
    if item.startswith("form "):
        return item + " unguarded"
    if item.startswith("script "):
        return item + " external"
    return item


def render(app, conclusions):
    """M15-C4: the ledger as one line (never more than 8): only what is open, then next."""
    c = conclusions or {}
    parts = []
    if c.get("missing"):
        parts.append("missing (from the ask's named ids): " + ", ".join(c["missing"]))
    if c.get("hidden"):
        parts.append("hidden: " + ", ".join(c["hidden"]))
    if c.get("unproven"):
        parts.append("unproven: " + ", ".join(c["unproven"]))
    elif c.get("proven") is False and c.get("next") == "probe":
        parts.append("unproven: no passing probe since the last open")
    if c.get("regressed"):
        parts.append("regressed: " + ", ".join(c["regressed"]))
    if c.get("contract"):
        parts.append("contract: " + ", ".join(_contract(item) for item in c["contract"]))
    probe = c.get("probe")
    if probe:
        text = "probe: %d passed, %d failed" % (probe.get("passed", 0), probe.get("failed", 0))
        if probe.get("failures"):
            text += " (%s)" % "; ".join(probe["failures"][:3])
        parts.append(text)
    parts.append("next: %s]" % c.get("next", "build"))
    return "[build ledger %s] " % app + " · ".join(parts)


# ---------------------------------------------------------------- the store and the worker

def _call(method, timeout=10, **params):
    # Only the install's own AtomSpace (IterBrow passes ITER_METTA_SOCKET to Iter): a test or a stray process
    # never reaches a store through the legacy default socket.
    if not os.environ.get("ITER_METTA_SOCKET"):
        raise RuntimeError("no AtomSpace socket (ITER_METTA_SOCKET) for the build ledger")
    from iterbrow_runtime.cognitive_events import _call_atomspace
    return _call_atomspace(method, timeout=timeout, **params)


def read(app):
    """{key: atom} of the app's build atoms ({} when the store cannot be read)."""
    try:
        return dict(_call("read_atoms", timeout=5, prefix=_prefix(app))["atoms"])
    except Exception:
        return {}


def _seed_units():
    if str(ITER_DIR) not in sys.path:
        sys.path.insert(0, str(ITER_DIR))
    from metta_server import _logical_units
    return list(_logical_units(SEED.read_text(encoding="utf-8")))


def worker_run(atoms):
    """`run(code)` over exactly `atoms` and the ledger's rules, in the one-shot Hyperon worker
    (iter/metta_query_worker.py): this app's facts only, whether or not the store has them yet."""
    def run(code):
        work = Path(tempfile.mkdtemp(prefix="ledger-"))
        payload = {"schema_version": 1, "epoch": 0, "commit": 0, "state_hash": "build-ledger", "seed_units": _seed_units(),
                   "atoms": dict(atoms), "code": code, "working_dir": str(work / "queries")}
        try:
            proc = subprocess.run([sys.executable, str(ITER_DIR / "metta_query_worker.py")], input=json.dumps(payload),
                                  text=True, capture_output=True, cwd=str(ITER_DIR), timeout=WORKER_TIMEOUT)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        response = json.loads(lines[-1]) if lines else {"ok": False, "error": proc.stderr[-300:]}
        if not response.get("ok"):
            raise RuntimeError(response.get("error") or "ledger query failed")
        return str(response.get("result", ""))
    return run


def _numbers(atoms, head):
    out = []
    for atom in atoms.values():
        found = re.match(r"^\(%s \S+ (\d+)" % head, atom)
        if found:
            out.append(int(found.group(1)))
    return out


def next_seq(atoms):
    return max(_numbers(atoms, "app-opened") + _numbers(atoms, "probe-run") + [0]) + 1


def observe(app, replace, stored=None, run=None):
    """Replace the app's families in `replace` ({family: [(key, atom)]}; "probe" adds a run and keeps the
    newest PROBE_RUNS_KEPT), conclude over all the app's facts, store facts and conclusions in one
    transaction. Returns (line, conclusions); the line ends " (not recorded)" when the write failed."""
    stored = read(app) if stored is None else dict(stored)
    merged = dict(stored)
    removals = []
    for family, facts in replace.items():
        prefix = _prefix(app, family)
        if family == "probe":
            runs = sorted({int(k[len(prefix):].split(":")[0]) for k in stored if k.startswith(prefix)})
            keep = set(runs[-(PROBE_RUNS_KEPT - 1):])
            old = [k for k in stored if k.startswith(prefix) and int(k[len(prefix):].split(":")[0]) not in keep]
        else:
            old = [k for k in stored if k.startswith(prefix)]
        for key in old:
            merged.pop(key, None)
        removals.extend(old)
        merged.update(dict(facts))
    facts_only = {k: v for k, v in merged.items() if not k.startswith((_prefix(app, "ledger"), _prefix(app, "line")))}
    conclusions = conclude(app, run or worker_run(facts_only))
    line = render(app, conclusions)
    operations = [{"op": "remove", "key": key} for key in removals if key not in merged]
    for facts in replace.values():
        operations.extend({"op": "upsert", "key": key, "atom": atom} for key, atom in facts)
    operations.append({"op": "upsert", "key": _prefix(app, "ledger") + "next",
                       "atom": "(ledger %s next %s %d)" % (app, conclusions["next"], int(time.time() * 1000))})
    operations.append({"op": "upsert", "key": _prefix(app, "line") + "text", "atom": "(ledger-line %s %s)" % (app, _q(line))})
    try:
        _call("transact", timeout=10, operations=operations, actor="iter", source="build_ledger",
              metadata={"domain": "build_ledger", "app": app})
    except Exception as error:
        print("[build ledger] %s not recorded: %s" % (app, error))
        return line + " (not recorded)", conclusions
    return line, conclusions


def asked(app, atoms=None):
    """The selectors the ask named (what the contract check looks for)."""
    atoms = read(app) if atoms is None else atoms
    out = []
    for key, atom in sorted(atoms.items()):
        if key.startswith(_prefix(app, "ask")):
            found = re.match(r'^\(ask-requires \S+ "((?:[^"\\]|\\.)*)"\)$', atom)
            if found:
                out.append(_unq(found.group(1)))
    return out


def observe_open(app, check):
    """browser_open_app: the check replaces the last one; the open becomes the newest."""
    stored = read(app)
    seq = next_seq(stored)
    line, _ = observe(app, {"check": facts_from_check(app, check),
                            "open": [(_prefix(app, "open") + str(seq), "(app-opened %s %d)" % (app, seq))]}, stored=stored)
    return line


def observe_probe(app, result, probe_json):
    """app_probe: a new run (and the check that ran before its steps). NACE learns from it (C6)."""
    stored = read(app)
    seq = next_seq(stored)
    replace = {"probe": facts_from_probe(app, result, probe_json, seq)}
    if result.get("check"):
        replace["check"] = facts_from_check(app, result["check"])
    line, conclusions = observe(app, replace, stored=stored)
    if not line.endswith("(not recorded)"):
        # A run after a re-open that followed an earlier run is a probe after an edit.
        runs, opens = _numbers(stored, "probe-run"), _numbers(stored, "app-opened")
        if runs and opens and max(opens) > max(runs):
            queue_pattern("edit_keeps_passing", "disconfirmed" if conclusions["regressed"] else "confirmed")
    return line


def record_ask(app, text, stored):
    """build_mode: add what the person's ask names. Ask facts grow while the app is built (a message that
    scrolled out of the request still asked for it); new_app and a vanished app clear them (C5).
    Returns True when something new was stored."""
    have = {atom for key, atom in stored.items() if key.startswith(_prefix(app, "ask"))}
    new = [atom for _key, atom in facts_from_ask(app, text) if atom not in have]
    if not new:
        return False
    used = {key for key in stored if key.startswith(_prefix(app, "ask"))}
    operations, index = [], 0
    for atom in new:
        while "%s%d" % (_prefix(app, "ask"), index) in used:
            index += 1
        used.add("%s%d" % (_prefix(app, "ask"), index))
        operations.append({"op": "upsert", "key": "%s%d" % (_prefix(app, "ask"), index), "atom": atom})
    _call("transact", timeout=5, operations=operations, actor="iter", source="build_ledger",
          metadata={"domain": "build_ledger", "app": app})
    return True


def stored_line(app, atoms):
    """(line, checked_at in ms) from the stored conclusions, or (None, None)."""
    found = re.match(r'^\(ledger-line \S+ "((?:[^"\\]|\\.)*)"\)$', atoms.get(_prefix(app, "line") + "text") or "")
    stamp = re.match(r"^\(ledger \S+ next \S+ (\d+)\)$", atoms.get(_prefix(app, "ledger") + "next") or "")
    if not found:
        return None, None
    return _unq(found.group(1)), (int(stamp.group(1)) if stamp else None)


def stored_next(app, atoms):
    found = re.match(r"^\(ledger \S+ next (\S+) \d+\)$", atoms.get(_prefix(app, "ledger") + "next") or "")
    return found.group(1) if found else None


def forget(apps):
    """M15-C5: remove every build atom of these apps (new_app starts clean; an app gone from the vault)."""
    keys = []
    for app in apps:
        if APP_ID.match(str(app)):
            keys.extend(read(app).keys())
    if keys:
        _call("transact", timeout=10, operations=[{"op": "remove", "key": key} for key in keys], actor="iter",
              source="build_ledger", metadata={"domain": "build_ledger"})
    return len(keys)


def built_apps():
    """App ids that have build atoms (empty when the store cannot be read)."""
    try:
        keys = _call("read_atoms", timeout=5, prefix="state:build:")["atoms"].keys()
    except Exception:
        return set()
    return {key.split(":")[2] for key in keys if key.count(":") >= 3}


# ---------------------------------------------------------------- NACE learns (C6)

PATTERN_LINES = {
    "probe_before_report": "(pending-revision pattern probe_before_report %s)\n",
    "edit_keeps_passing": "(pending-revision pattern edit_keeps_passing %s)\n",
}


def queue_pattern(name, outcome, root=None):
    """M15-C6: one `(pending-revision pattern <name> confirmed|disconfirmed)` line in nace_pending.metta — the
    queue the courier already revises, written exactly as idle_cycle_detector writes its own."""
    if name not in PATTERN_LINES or outcome not in ("confirmed", "disconfirmed"):
        return False
    path = Path(root or os.environ.get("ITER_DIR") or ITER_DIR) / "nace_pending.metta"
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(PATTERN_LINES[name] % outcome)
        return True
    except OSError:
        return False


def learn_from_report(app, atoms):
    """At a report (a send while building): probe_before_report is confirmed when the stored ledger says
    report, disconfirmed otherwise; nothing without a ledger for the app."""
    nxt = stored_next(app, atoms)
    if nxt is None:
        return None
    outcome = "confirmed" if nxt == "report" else "disconfirmed"
    queue_pattern("probe_before_report", outcome)
    return outcome
