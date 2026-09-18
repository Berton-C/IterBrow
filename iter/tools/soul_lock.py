"""Soul Namespace Mutation Lock â ClarityOmega transactional protocol.
Provides begin/commit/rollback for soul namespace changes.
Lock prevents concurrent mutation of space.metta, soul_eval, soul_check.
"""

import json, os, time

DESCRIPTION = "Soul namespace mutation lock: transactional protocol for soul changes. begin â verify â commit/rollback."

LOCK_PATH = "memory/soul_lock.json"
# STAGE 4 (2026-09-14): dropped "space.metta" -- that file doesn't exist in
# this repo, so it was a dead reference that made every single verify() call
# report a false "missing" issue regardless of real soul state. Added
# nace_beliefs.metta and capability_lifecycle.metta: belief/lifecycle
# mutations (nace_courier.py's belief writes, capability trust-stage
# overrides) are as load-bearing to the Soul's real behavior as the four
# files already protected here, so they get the same backup/rollback
# discipline instead of being plain unprotected writes.
SOUL_FILES = [
    "tools/soul_eval.py",
    "transformations/soul_check.py",
    "transformations/soul_voice.py",
    "nace_beliefs.metta",
    "capability_lifecycle.metta",
]

def _load_lock():
    try:
        with open(LOCK_PATH) as f:
            return json.load(f)
    except:
        return {"status": "unlocked", "holder": None, "timestamp": None, "backups": {}}

def _save_lock(data):
    with open(LOCK_PATH, "w") as f:
        json.dump(data, f)

def _backup_files():
    """Create backups of all soul files before mutation.

    FIX (2026-09-17 audit): the bare except:pass here used to swallow any
    copy failure -- a soul file could silently end up with no backup while
    the caller still saw an apparently-successful "locked" status. Now
    returns the failures too, so begin() can refuse to open a lock it
    cannot actually guarantee a rollback for.
    """
    backups = {}
    failed = []
    for rel_path in SOUL_FILES:
        full = os.path.join(".", rel_path)
        if os.path.exists(full):
            bak_path = full + ".lockbak"
            try:
                import shutil
                shutil.copy2(full, bak_path)
                backups[rel_path] = bak_path
            except Exception as e:
                failed.append({"file": rel_path, "error": "%s: %s" % (type(e).__name__, e)})
    return backups, failed

def _restore_files(backups):
    """Restore from backups (rollback).

    FIX (2026-09-17 audit): the bare except:pass here used to swallow
    restore failures -- rollback always reported "rolled_back"/"Files
    restored" even when copy2() actually failed and the mutated file was
    still live on disk. This is the exact silent-failure pattern this
    audit was asked to find. Now returns which files actually got
    restored vs. which failed.
    """
    restored = []
    failed = []
    for rel_path, bak_path in backups.items():
        full = os.path.join(".", rel_path)
        try:
            import shutil
            shutil.copy2(bak_path, full)
            restored.append(rel_path)
        except Exception as e:
            failed.append({"file": rel_path, "error": "%s: %s" % (type(e).__name__, e)})
    return restored, failed

def _cleanup_backups(backups):
    """Remove backup files after successful commit.

    Non-fatal if a backup cannot be removed (the mutation itself is
    unaffected), but now reports which ones failed instead of hiding it.
    """
    failed = []
    for rel_path, bak_path in backups.items():
        try:
            os.remove(bak_path)
        except Exception as e:
            failed.append({"file": rel_path, "error": "%s: %s" % (type(e).__name__, e)})
    return failed

def run(action="status", holder="soul_eval"):
    lock = _load_lock()
    
    if action == "status":
        return json.dumps({
            "status": lock.get("status", "unlocked"),
            "holder": lock.get("holder"),
            "timestamp": lock.get("timestamp"),
            "protected_files": SOUL_FILES,
        })
    
    elif action == "begin":
        if lock.get("status") == "locked":
            return json.dumps({"error": "Lock already held", "holder": lock.get("holder")})
        backups, backup_failures = _backup_files()
        # FIX (2026-09-17 audit): a lock used to open even when a soul file
        # failed to back up, which meant a later rollback would silently
        # have nothing to restore that file from. Refuse to open the lock
        # at all in that case -- an honest "cannot safely start" beats a
        # lock that cannot actually guarantee its own rollback.
        if backup_failures:
            return json.dumps({
                "error": "Could not open lock: backup failed for one or more soul files",
                "backup_failures": backup_failures,
            })
        lock = {
            "status": "locked",
            "holder": holder,
            "timestamp": int(time.time()),
            "backups": backups,
            "expiry": 20,  # cycles
        }
        _save_lock(lock)
        return json.dumps({"status": "locked", "backups": list(backups.keys())})
    
    elif action == "commit":
        if lock.get("status") != "locked":
            return json.dumps({"error": "No active lock to commit"})
        backups = lock.get("backups", {})
        cleanup_failures = _cleanup_backups(backups)
        lock = {"status": "unlocked", "holder": None, "timestamp": None, "backups": {}}
        _save_lock(lock)
        result = {"status": "committed", "message": "Soul mutation committed."}
        if cleanup_failures:
            # Non-fatal: the mutation itself already succeeded, only a
            # leftover .lockbak file could not be removed. Reported (not
            # swallowed) so it does not silently accumulate stale backups.
            result["message"] = "Soul mutation committed. Some backup files could not be cleaned up."
            result["cleanup_failures"] = cleanup_failures
        else:
            result["message"] = "Soul mutation committed. Backups cleaned."
        return json.dumps(result)
    
    elif action == "rollback":
        if lock.get("status") != "locked":
            return json.dumps({"error": "No active lock to rollback"})
        backups = lock.get("backups", {})
        restored, restore_failures = _restore_files(backups)
        _cleanup_backups(backups)
        lock = {"status": "unlocked", "holder": None, "timestamp": None, "backups": {}}
        _save_lock(lock)
        # FIX (2026-09-17 audit): this used to unconditionally report
        # "rolled_back" / "Files restored" even when copy2() failed --
        # the exact silent-failure this audit was asked to find. A file
        # that failed to restore is left mutated on disk while the caller
        # is told rollback succeeded. Now the status and message reflect
        # what actually happened.
        if restore_failures:
            return json.dumps({
                "status": "rollback_incomplete",
                "message": "Rollback incomplete: one or more soul files could not be restored. They remain in their mutated state.",
                "restored": restored,
                "restore_failures": restore_failures,
            })
        return json.dumps({"status": "rolled_back", "message": "Soul mutation rolled back. Files restored.", "restored": restored})
    
    elif action == "verify":
        """Verify soul namespace integrity after mutation."""
        issues = []
        for rel_path in SOUL_FILES:
            full = os.path.join(".", rel_path)
            if not os.path.exists(full):
                issues.append({"file": rel_path, "issue": "missing"})
            elif os.path.getsize(full) == 0:
                issues.append({"file": rel_path, "issue": "empty"})
        if issues:
            return json.dumps({"verified": False, "issues": issues})
        return json.dumps({"verified": True, "issues": []})
    
    else:
        return json.dumps({"error": "Unknown action: %s" % action})
