"""
Self-Improve Tool - DGM-style self-improvement for Iter.

Features:
  - Fitness snapshot: measures reliability, memory efficiency, context utilization
  - Fitness compare: compares snapshots, computes composite delta with effect sizing
  - Experiment ledger: logs each experiment with file hashes and outcomes
  - Champion tracking: keeps best-known configuration with backward-compat
  - Apply: backup â write â validate (compile, regression, integrity)
  - Revert: restore from backup on failure or degradation
  - Full loop: snapshot â apply â validate â snapshot â compare â accept/revert

MicroPython-compatible: no os.path.getsize, no asyncio, manual hex.
"""
import os, json, sys, time, hashlib

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _memory_guard as _guard
import _memory_projection as _projection  # single source of truth for "what counts as prompt memory"
import soul_lock as _soul_lock  # SOUL_FILES + lock state: the design's existing notion of constitutional files

# ---- Constitutional gate (2026-09-17) ----
# Before this, apply/full_loop consulted NO protected list: a single call could
# overwrite a soul file, this tool, or the fitness ruler (_memory_projection.py)
# with nothing but a compile check, and full_loop would then CROWN the result if
# the number went up. The DGM premise (the improver may improve itself) is kept:
# these files are still writable -- but only while the soul lock is held, so the
# change goes through soul_lock's backups and an explicit commit/rollback. This is
# a guardrail on the sanctioned path, not an OS boundary; `revert` is deliberately
# NOT gated (undo must never require the lock that let the change through).
GATED_EXTRA = [
    "iter.py",                     # core loop; --invoke re-executes it per tool call, so a hot-load creates mixed state
    "tools/self_improve.py",       # the referee
    "tools/_memory_projection.py", # the ruler
    "tools/_memory_guard.py",      # the content-mutation guard
]

def _gated_paths():
    out = set()
    for rel in list(_soul_lock.SOUL_FILES) + GATED_EXTRA:
        out.add(os.path.realpath(os.path.join(ITER_ROOT, rel)))
    return out

def _gate_check(target):
    """Return None if `target` may be written now, else an error dict.
    Gated files require memory/soul_lock.json status == "locked" (any holder;
    the holder is recorded in the ledger by the caller)."""
    real = os.path.realpath(target)
    if real not in _gated_paths():
        return None
    lock = _soul_lock._load_lock()
    if lock.get("status") == "locked":
        return None
    return {
        "error": "constitutional file: soul lock required",
        "target": target,
        "how_to": "call soul_lock action=begin first (backs up all SOUL_FILES), then re-run this "
                  "apply/full_loop, then soul_lock action=commit to keep or action=rollback to undo. "
                  "revert is never gated.",
        "gated_files": sorted(os.path.relpath(p, os.path.realpath(ITER_ROOT)) for p in _gated_paths()),
    }

def _lock_holder():
    try:
        return _soul_lock._load_lock().get("holder")
    except Exception:
        return None

def _targets_memory(target):
    """True if the file being changed lives under memory/ -- shrinking the corpus
    by editing/deleting it must not read as a memory_efficiency gain."""
    real = os.path.realpath(target)
    mem = os.path.realpath(os.path.join(ITER_ROOT, "memory"))
    return real == mem or real.startswith(mem + os.sep)

DESCRIPTION = ("DGM-style self-improvement: fitness snapshots, experiment ledger, "
               "champion tracking with backward-compatible key migration, "
               "safe apply/revert with 3-level validation.")

ITER_ROOT = "."
CHAMPION_PATH = os.path.join(ITER_ROOT, "memory", "champion.json")
LOG_PATH = os.path.join(ITER_ROOT, "memory", "self_improve_log.json")
MEMORY_DIR = os.path.join(ITER_ROOT, "memory")
BACKUP_DIR = os.path.join(ITER_ROOT, "memory", "self_improve_backups")
# FIX (2026-09-17 audit): this used to point at memory/regression_tests.json,
# which tools/eval.py *also* writes to -- but eval.py writes a run-results
# log there ({"ts": ..., "t": [{"test": ..., "pass": ...}, ...]}), not the
# {name: python_source} shape _validate_regression() below expects. Every
# real apply()/full_loop() call read eval.py's file, iterated its two keys
# ("ts", "t") as if they were test names, tried to exec() a float and a list
# as Python source, and always failed both -- meaning Level 2 validation
# could never pass, and auto_revert (default True) reverted every real
# candidate change regardless of its actual quality. Confirmed via
# self_improve_log.json: 2 lifetime entries, both action=record with
# files_changed=[], i.e. apply/full_loop has never completed a real change.
# Given self_improve.py its own file so the two tools stop colliding.
REGRESSION_PATH = os.path.join(ITER_ROOT, "memory", "self_improve_regression_tests.json")
MAX_MEMORY_CHARS = 20000  # kept in sync with iter.py's cap

# ---- MicroPython compat helpers ----

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _file_size(path):
    try:
        return os.stat(path)[6]
    except OSError:
        return 0

# Binary/media extensions excluded from the text-memory measure -- kept in
# sync with transformations/auto_improve.py's _dir_size_chars (2026-09-14 fix).
_BINARY_EXTS = (
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico",
    ".pdf", ".zip", ".gz", ".tar", ".tgz", ".mp4", ".mp3", ".wav",
)


def _dir_size(path):
    total = 0
    try:
        for entry in os.listdir(path):
            if entry.startswith("."):
                continue
            full = os.path.join(path, entry)
            try:
                st = os.stat(full)
                if st[0] & 0x4000:
                    total += _dir_size(full)
                elif entry.lower().endswith(_BINARY_EXTS):
                    continue
                else:
                    total += st[6]
            except OSError:
                pass
    except OSError:
        pass
    return total

def _read_file(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception:
        return ""

def _write_file(path, content):
    try:
        _guard.check_open(path, "w")
    except PermissionError:
        return False
    try:
        with open(path, "w") as f:
            f.write(content)
        return True
    except Exception:
        return False

def _read_json(path):
    try:
        return json.loads(_read_file(path))
    except Exception:
        return {}

def _write_json(path, data):
    return _write_file(path, json.dumps(data))

def _sha256_hex(data_bytes):
    h = hashlib.sha256()
    h.update(data_bytes)
    raw = h.digest()
    return "".join("%02x" % b for b in raw)

def _file_hash(path):
    try:
        with open(path, "rb") as f:
            return _sha256_hex(f.read())
    except Exception:
        return ""

def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def _ensure_dir(path):
    if not _exists(path):
        try:
            os.mkdir(path)
        except OSError:
            pass

# ---- Champion management ----

def _load_champion():
    if not _exists(CHAMPION_PATH):
        return None
    try:
        champ = json.loads(_read_file(CHAMPION_PATH))
        # Backward-compat: migrate short keys to full keys
        if "bc" in champ and "best_composite" not in champ:
            champ["best_composite"] = champ.pop("bc")
        if "at" in champ and "set_at" not in champ:
            champ["set_at"] = champ.pop("at")
        if "by" in champ and "set_by" not in champ:
            champ["set_by"] = champ.pop("by")
        return champ
    except (ValueError, OSError, KeyError):
        return None

def _save_champion(champ):
    return _write_json(CHAMPION_PATH, champ)

# ---- Fitness measurement ----

WEIGHTS = {"reliability": 0.4, "memory_efficiency": 0.3, "context_utilization": 0.3}

def fitness_snapshot():
    snap = {}
    # Reliability: from tool_reliability runtime JSON
    rel_path = os.path.join(ITER_ROOT, "transformations", ".runtime", "tool_reliability.json")
    rel = _read_json(rel_path)
    if rel:
        scores = []
        for tname, tdata in rel.items():
            f = tdata.get("f", 1.0)
            c = tdata.get("c", 0.0)
            calls = tdata.get("calls", 0)
            if calls >= 2:
                scores.append(f * c)
        snap["reliability"] = sum(scores) / len(scores) if scores else 0.5
    else:
        snap["reliability"] = 0.5
    # Memory efficiency: how close to budget.
    # FIX 2026-09-17: measure the PROMPT PROJECTION (what iter.py actually
    # compares against MAX_MEMORY_CHARS), not the raw folder. The raw walk
    # counted ~1 MB of on-disk storage (story_journal web app, localStorage
    # dumps, logs) that never reaches the prompt, pinning this dimension at
    # 0.0 and making the champion unreachable. Rule lives in
    # tools/_memory_projection.py, shared with iter.py and auto_improve.py.
    mem_size = _projection.projection_chars(MEMORY_DIR)
    snap["memory_efficiency"] = max(0.0, min(1.0, 1.0 - (mem_size / (MAX_MEMORY_CHARS * 3))))
    # Context utilization: fraction of tier content used (simplified)
    snap["context_utilization"] = 0.5  # default; could be enhanced
    # Composite
    composite = sum(WEIGHTS.get(k, 0) * v for k, v in snap.items())
    snap["composite"] = composite
    snap["timestamp"] = _now()
    return snap

def fitness_compare(prev, curr):
    if not prev or not curr:
        return {"delta_composite": 0.0, "delta_dimensions": {}, "effect": "unknown"}
    delta_c = curr.get("composite", 0.0) - prev.get("composite", 0.0)
    deltas = {}
    for dim in WEIGHTS:
        deltas[dim] = curr.get(dim, 0.0) - prev.get(dim, 0.0)
    # Effect size: Cohen's d approximation (simple delta / 0.5 spread)
    spread = 0.5
    effect_size = abs(delta_c) / spread if spread > 0 else 0.0
    if effect_size < 0.2:
        effect = "negligible"
    elif effect_size < 0.5:
        effect = "small"
    elif effect_size < 0.8:
        effect = "medium"
    else:
        effect = "large"
    return {"delta_composite": delta_c, "delta_dimensions": deltas, "effect": effect, "effect_size": effect_size}

# ---- Logging ----

def _read_log():
    try:
        data = json.loads(_read_file(LOG_PATH))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []

def _append_log(entry):
    log = _read_log()
    log.append(entry)
    if len(log) > 100:
        log = log[-80:]
    _write_json(LOG_PATH, log)

def _hash_all_tools():
    hashes = {}
    tools_dir = os.path.join(ITER_ROOT, "tools")
    try:
        for name in os.listdir(tools_dir):
            if name.endswith(".py") and not name.startswith("_"):
                hashes[name] = _file_hash(os.path.join(tools_dir, name))
    except OSError:
        pass
    return hashes

# ---- Validation (3-level) ----

def _validate_compile(filepath):
    """Level 1: Smoke test â does the file compile?"""
    try:
        source = _read_file(filepath)
        if not source.strip():
            return False, "file is empty"
        compile(source, filepath, "exec")
        return True, "compile OK"
    except SyntaxError as e:
        return False, "syntax error: " + str(e)
    except Exception as e:
        return False, "compile error: " + str(e)

def _validate_regression():
    """Level 2: Run regression tests from self_improve_regression_tests.json
    (this tool's own file -- do not confuse with eval.py's
    memory/regression_tests.json, an unrelated run-results log)."""
    tests = _read_json(REGRESSION_PATH)
    if not tests:
        return True, "no regression tests defined"
    passed = 0
    failed = 0
    failures = []
    for name, test_code in tests.items():
        try:
            # Each test is Python source that should evaluate without error
            # and return a truthy value.
            ns = {}
            exec(test_code, ns)
            result = ns.get("result", True)
            if result:
                passed += 1
            else:
                failed += 1
                failures.append(name)
        except Exception as e:
            failed += 1
            failures.append(name + ": " + str(e))
    if failed == 0:
        return True, "all " + str(passed) + " regression tests passed"
    return False, str(failed) + "/" + str(passed + failed) + " tests failed: " + ", ".join(failures)

def _validate_integrity(filepath):
    """Level 3: Integrity check â file exists, has content, and hash matches."""
    if not _exists(filepath):
        return False, "file does not exist"
    size = _file_size(filepath)
    if size == 0:
        return False, "file is empty (0 bytes)"
    return True, "integrity OK (" + str(size) + " bytes)"

def _run_validation(filepath):
    """Run all 3 validation levels. Returns (all_passed, details dict)."""
    results = {}
    all_passed = True

    ok, msg = _validate_compile(filepath)
    results["compile"] = {"passed": ok, "message": msg}
    if not ok:
        all_passed = False

    ok, msg = _validate_regression()
    results["regression"] = {"passed": ok, "message": msg}
    if not ok:
        all_passed = False

    ok, msg = _validate_integrity(filepath)
    results["integrity"] = {"passed": ok, "message": msg}
    if not ok:
        all_passed = False

    results["all_passed"] = all_passed
    return all_passed, results

# ---- Backup / Restore ----

def _make_backup(filepath):
    """Create a timestamped backup of filepath. Returns backup path or None."""
    _ensure_dir(BACKUP_DIR)
    if not _exists(filepath):
        return None
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    basename = os.path.basename(filepath).replace(".", "_")
    backup_path = os.path.join(BACKUP_DIR, basename + "_" + ts + ".bak")
    # FIX 2026-09-17: one-second timestamp resolution meant two applies to
    # the same target within a second reused the same path, and the second
    # backup silently overwrote the first (observed in the /tmp drill run).
    # Never overwrite an existing backup: add a numeric suffix instead.
    n = 1
    while _exists(backup_path):
        backup_path = os.path.join(BACKUP_DIR, basename + "_" + ts + "_" + str(n) + ".bak")
        n += 1
    content = _read_file(filepath)
    if _write_file(backup_path, content):
        return backup_path
    return None

def _restore_backup(backup_path, target_path):
    """Restore file from backup. Returns True on success."""
    if not _exists(backup_path):
        return False
    content = _read_file(backup_path)
    return _write_file(target_path, content)

def _list_backups():
    """List all backup files."""
    _ensure_dir(BACKUP_DIR)
    backups = []
    try:
        for name in os.listdir(BACKUP_DIR):
            if name.endswith(".bak"):
                full = os.path.join(BACKUP_DIR, name)
                backups.append({
                    "file": name,
                    "path": full,
                    "size": _file_size(full),
                    "hash": _file_hash(full),
                })
    except OSError:
        pass
    return sorted(backups, key=lambda b: b["file"], reverse=True)

# ---- Main run ----

def _coerce_bool(value, default=True):
    """Schema types every parameter as string, so "false" must not be truthy."""
    if isinstance(value, bool):
        return value
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() not in ("false", "0", "no", "off", "n")


def _coerce_list(value):
    """Accept a JSON array string, a comma-separated string, or a real list."""
    if isinstance(value, list):
        return value
    if value is None or str(value).strip() == "":
        return []
    text = str(value).strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except ValueError:
            pass
    return [p.strip() for p in text.split(",") if p.strip()]


def run(action="snapshot", target="", content="", description="", backup="",
        prev="", curr="", prev_snapshot="", curr_snapshot="", files_changed="",
        auto_revert="", revert_on_degradation=""):
    """Entry point.

    FIX (2026-09-17 audit, root cause of "hot-load/rollback never fired"):
    this used to be `def run(action="snapshot", **kwargs)`. iter.py builds
    each tool's schema from inspect.signature(run) -- it advertises every
    parameter NAME as a required string property with additionalProperties
    False. `**kwargs` therefore showed up to the model as a single string
    field literally named "kwargs", and target/content/description/etc. were
    never exposed at all. Any JSON the model stuffed into that field arrived
    here as kwargs["kwargs"] = "<string>", so kwargs.get("target") was always
    None and apply/full_loop/revert/compare/record returned
    {"error": "missing 'target' argument"} on every attempt. Only the
    no-argument actions (snapshot, champion, backups, log, dry_run) were
    ever reachable -- which is exactly the set of actions present in the
    lifetime ledger. Reproduced live during the 2026-09-17 verification
    drill (3 identical failures on STEP 2).

    Parameters are now declared explicitly so the schema exposes them. The
    body below is unchanged: it still reads from a `kwargs` dict, which is
    rebuilt here from the named parameters. Booleans and lists are coerced
    because the schema delivers everything as strings ("false" would
    otherwise be truthy and defeat auto_revert).
    """
    action = action or "snapshot"
    kwargs = {
        "target": target or "",
        "content": content if content is not None else "",
        "description": description or "",
        "backup": backup or "",
        "prev": prev if prev not in ("", None) else None,
        "curr": curr if curr not in ("", None) else None,
        "prev_snapshot": prev_snapshot if prev_snapshot not in ("", None) else None,
        "curr_snapshot": curr_snapshot if curr_snapshot not in ("", None) else None,
        "files_changed": _coerce_list(files_changed),
        "auto_revert": _coerce_bool(auto_revert, True),
        "revert_on_degradation": _coerce_bool(revert_on_degradation, True),
    }

    if action == "snapshot":
        snap = fitness_snapshot()
        return json.dumps(snap)

    if action == "compare":
        prev = kwargs.get("prev")
        curr = kwargs.get("curr")
        if isinstance(prev, str):
            prev = json.loads(prev)
        if isinstance(curr, str):
            curr = json.loads(curr)
        result = fitness_compare(prev, curr)
        return json.dumps(result)

    if action == "champion":
        champ = _load_champion()
        if champ:
            return json.dumps(champ)
        return json.dumps({"status": "no champion set"})

    if action == "apply":
        """Safe change: backup â write â validate. Auto-revert on failure.

        Args (via kwargs):
          target: path to the file to modify (relative to ITER_ROOT or absolute)
          content: new file content
          auto_revert: if True (default), revert on validation failure

        Returns JSON with validation results and whether reverted.
        """
        target = kwargs.get("target", "")
        content = kwargs.get("content", "")
        auto_revert = kwargs.get("auto_revert", True)

        if not target:
            return json.dumps({"error": "missing 'target' argument"})
        if content is None:
            return json.dumps({"error": "missing 'content' argument"})

        # Resolve path
        if not target.startswith("/"):
            target = os.path.join(ITER_ROOT, target)

        blocked = _gate_check(target)
        if blocked:
            return json.dumps(blocked)

        # Step 1: Backup
        backup_path = _make_backup(target)
        if not backup_path:
            return json.dumps({
                "error": "backup failed (file may not exist)",
                "target": target,
            })

        # Step 2: Write new content
        if not _write_file(target, content):
            return json.dumps({
                "error": "write failed",
                "target": target,
                "backup": backup_path,
            })

        # Step 3: Validate
        all_passed, results = _run_validation(target)

        response = {
            "target": target,
            "backup": backup_path,
            "validation": results,
            "reverted": False,
        }

        # Step 4: Auto-revert if validation failed
        if not all_passed and auto_revert:
            restored = _restore_backup(backup_path, target)
            response["reverted"] = restored
            response["revert_reason"] = "validation failed"

        return json.dumps(response)

    if action == "revert":
        """Restore a file from a backup.

        Args:
          backup: backup file path (from apply response)
          target: original file path (where to restore)
        """
        backup = kwargs.get("backup", "")
        target = kwargs.get("target", "")

        if not backup:
            # Try to find most recent backup for target
            if target:
                if not target.startswith("/"):
                    target = os.path.join(ITER_ROOT, target)
                basename = os.path.basename(target).replace(".", "_")
                backups = _list_backups()
                for b in backups:
                    if b["file"].startswith(basename):
                        backup = b["path"]
                        break
            if not backup:
                return json.dumps({"error": "no backup specified or found"})

        if not target:
            # Derive target from backup name
            basename = os.path.basename(backup)
            # Format: name_ext_TIMESTAMP.bak â name.ext
            parts = basename.rsplit("_", 1)  # split off timestamp.bak
            if len(parts) == 2:
                name_part = parts[0]
                # Restore dots: convert name_ext â name.ext
                last_underscore = name_part.rfind("_")
                if last_underscore >= 0:
                    target = name_part[:last_underscore] + "." + name_part[last_underscore + 1:]
                    target = os.path.join(ITER_ROOT, target)

        if not target:
            return json.dumps({"error": "could not determine target path"})

        restored = _restore_backup(backup, target)
        return json.dumps({
            "restored": restored,
            "backup": backup,
            "target": target,
        })

    if action == "backups":
        """List available backups."""
        return json.dumps(_list_backups())

    if action == "full_loop":
        """Complete DGM cycle: snapshot â apply â validate â snapshot â compare â accept/revert.

        Args:
          target: file to modify
          content: new content
          description: experiment description
          revert_on_degradation: if True (default), revert if fitness decreased

        Returns full experiment report.
        """
        target = kwargs.get("target", "")
        content = kwargs.get("content", "")
        description = kwargs.get("description", "")
        revert_on_degradation = kwargs.get("revert_on_degradation", True)

        if not target or content is None:
            return json.dumps({"error": "missing 'target' or 'content'"})

        if not target.startswith("/"):
            target = os.path.join(ITER_ROOT, target)

        blocked = _gate_check(target)
        if blocked:
            return json.dumps(blocked)
        gated_under_lock = os.path.realpath(target) in _gated_paths()

        # Step 1: Pre-snapshot
        pre_snap = fitness_snapshot()

        # Step 2: Backup
        backup_path = _make_backup(target)
        if not backup_path:
            return json.dumps({
                "error": "backup failed",
                "target": target,
            })

        # Step 3: Write new content
        if not _write_file(target, content):
            return json.dumps({
                "error": "write failed",
                "target": target,
                "backup": backup_path,
            })

        # Step 4: Validate
        all_passed, val_results = _run_validation(target)

        if not all_passed:
            # Validation failed â revert
            restored = _restore_backup(backup_path, target)
            _append_log({
                "timestamp": _now(),
                "description": description,
                "target": target,
                "outcome": "reverted (validation failed)",
                "validation": val_results,
                "backup": backup_path,
            })
            return json.dumps({
                "target": target,
                "backup": backup_path,
                "validation": val_results,
                "reverted": restored,
                "revert_reason": "validation failed",
                "pre_snapshot": pre_snap,
            })

        # Step 5: Post-snapshot
        post_snap = fitness_snapshot()

        # Step 6: Compare
        comparison = fitness_compare(pre_snap, post_snap)

        # Step 6b (2026-09-17): a change whose TARGET is memory/ content cannot
        # earn memory_efficiency credit -- deleting or trimming the corpus is not
        # efficiency, it is amputation. Zero that dimension's delta and recompute
        # the composite delta from the remaining weighted dimensions. Neutral
        # outcomes are still accepted (delta >= 0); they are simply never crowned
        # for shrinking memory.
        scoring_note = ""
        zeroed_mem_delta = 0.0
        if _targets_memory(target):
            dims = comparison.get("delta_dimensions", {})
            if dims.get("memory_efficiency", 0.0) != 0.0:
                zeroed_mem_delta = dims["memory_efficiency"]
                scoring_note = ("memory_efficiency delta %.4f zeroed: target is memory/ content"
                                % zeroed_mem_delta)
                dims["memory_efficiency"] = 0.0
                comparison["delta_composite"] = sum(WEIGHTS.get(k, 0.0) * v for k, v in dims.items())
                comparison["scoring_note"] = scoring_note

        # Step 7: Decide â accept or revert
        improved = comparison["delta_composite"] >= 0
        reverted = False
        revert_reason = ""

        if not improved and revert_on_degradation:
            restored = _restore_backup(backup_path, target)
            reverted = restored
            revert_reason = "fitness degraded (delta=" + str(comparison["delta_composite"]) + ")"

        # Step 8: Record experiment
        entry = {
            "timestamp": _now(),
            "description": description,
            "target": target,
            "files_changed": [target],
            "pre_composite": pre_snap.get("composite", 0.0),
            "post_composite": post_snap.get("composite", 0.0),
            "delta_composite": comparison.get("delta_composite", 0.0),
            "effect": comparison.get("effect", "unknown"),
            "outcome": "reverted" if reverted else "accepted",
            "backup": backup_path,
            "file_hashes": _hash_all_tools(),
        }
        if scoring_note:
            entry["scoring_note"] = scoring_note
        if gated_under_lock:
            entry["constitutional"] = True
            entry["lock_holder"] = _lock_holder()
        _append_log(entry)

        # Step 9: Update champion if accepted and improved
        if not reverted and improved:
            champ = _load_champion() or {
                "best_composite": 0.0,
                "best_per_dimension": {},
                "file_hashes": {},
                "set_at": "",
                "set_by": "initial",
                "history": [],
            }
            # The crown check must see the SAME adjustment as the accept decision:
            # a memory/-content change gets no memory_efficiency credit here either,
            # otherwise an amputation whose raw composite tops the champion would
            # still be crowned (caught by the 2026-09-17 /tmp drill, case H).
            crown_composite = post_snap.get("composite", 0.0) - WEIGHTS.get("memory_efficiency", 0.0) * zeroed_mem_delta
            if crown_composite > champ.get("best_composite", 0.0):
                champ["best_composite"] = crown_composite
                champ["best_per_dimension"] = {k: post_snap.get(k, 0.0) for k in WEIGHTS}
                if zeroed_mem_delta:
                    champ["best_per_dimension"]["memory_efficiency"] = pre_snap.get("memory_efficiency", 0.0)
                champ["file_hashes"] = entry["file_hashes"]
                champ["set_at"] = _now()
                champ["set_by"] = "self_improve"
                champ.setdefault("history", []).append({
                    "timestamp": _now(),
                    "composite": post_snap["composite"],
                    "delta": comparison.get("delta_composite", 0.0),
                    "description": description,
                })
                _save_champion(champ)
                entry["new_champion"] = True

        return json.dumps({
            "target": target,
            "backup": backup_path,
            "validation": val_results,
            "pre_snapshot": pre_snap,
            "post_snapshot": post_snap,
            "comparison": comparison,
            "reverted": reverted,
            "revert_reason": revert_reason,
            "experiment": entry,
        })

    if action == "record":
        # Record an experiment result (manual, without apply/revert)
        prev_snap = kwargs.get("prev_snapshot")
        curr_snap = kwargs.get("curr_snapshot")
        files_changed = kwargs.get("files_changed", [])
        description = kwargs.get("description", "")
        if isinstance(prev_snap, str):
            prev_snap = json.loads(prev_snap) if prev_snap else None
        if isinstance(curr_snap, str):
            curr_snap = json.loads(curr_snap) if curr_snap else None
        if not curr_snap:
            curr_snap = fitness_snapshot()
        if not prev_snap:
            champ = _load_champion()
            prev_snap = champ if champ else {}
        comparison = fitness_compare(prev_snap, curr_snap)
        entry = {
            "timestamp": _now(),
            "description": description,
            "files_changed": files_changed,
            "prev_composite": prev_snap.get("composite", 0.0) if prev_snap else 0.0,
            "curr_composite": curr_snap.get("composite", 0.0),
            "delta_composite": comparison.get("delta_composite", 0.0),
            "effect": comparison.get("effect", "unknown"),
            "file_hashes": _hash_all_tools(),
        }
        _append_log(entry)
        # Update champion if improved
        champ = _load_champion() or {
            "best_composite": 0.0,
            "best_per_dimension": {},
            "file_hashes": {},
            "set_at": "",
            "set_by": "initial",
            "history": [],
        }
        if curr_snap.get("composite", 0.0) > champ.get("best_composite", 0.0):
            champ["best_composite"] = curr_snap["composite"]
            champ["best_per_dimension"] = {k: curr_snap.get(k, 0.0) for k in WEIGHTS}
            champ["file_hashes"] = entry["file_hashes"]
            champ["set_at"] = _now()
            champ["set_by"] = "self_improve"
            champ.setdefault("history", []).append({
                "timestamp": _now(),
                "composite": curr_snap["composite"],
                "delta": comparison.get("delta_composite", 0.0),
                "description": description,
            })
            _save_champion(champ)
            entry["new_champion"] = True
        return json.dumps(entry)

    if action == "log":
        log = _read_log()
        return json.dumps(log[-10:] if len(log) > 10 else log)

    if action == "dry_run":
        # Verify everything works without side effects
        snap = fitness_snapshot()
        champ = _load_champion()
        log = _read_log()
        backups = _list_backups()
        return json.dumps({
            "status": "ok",
            "snapshot_keys": list(snap.keys()),
            "champion_loaded": champ is not None,
            "log_entries": len(log),
            "backups_available": len(backups),
            "micropython_compat": True,
            "actions": ["snapshot", "compare", "champion", "apply", "revert",
                        "backups", "full_loop", "record", "log", "dry_run"],
        })

    return json.dumps({"error": "unknown action: " + action})
