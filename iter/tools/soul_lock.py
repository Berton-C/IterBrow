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
    """Create backups of all soul files before mutation."""
    backups = {}
    for rel_path in SOUL_FILES:
        full = os.path.join(".", rel_path)
        if os.path.exists(full):
            bak_path = full + ".lockbak"
            try:
                import shutil
                shutil.copy2(full, bak_path)
                backups[rel_path] = bak_path
            except:
                pass
    return backups

def _restore_files(backups):
    """Restore from backups (rollback)."""
    for rel_path, bak_path in backups.items():
        full = os.path.join(".", rel_path)
        try:
            import shutil
            shutil.copy2(bak_path, full)
        except:
            pass

def _cleanup_backups(backups):
    """Remove backup files after successful commit."""
    for rel_path, bak_path in backups.items():
        try:
            os.remove(bak_path)
        except:
            pass

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
        backups = _backup_files()
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
        _cleanup_backups(backups)
        lock = {"status": "unlocked", "holder": None, "timestamp": None, "backups": {}}
        _save_lock(lock)
        return json.dumps({"status": "committed", "message": "Soul mutation committed. Backups cleaned."})
    
    elif action == "rollback":
        if lock.get("status") != "locked":
            return json.dumps({"error": "No active lock to rollback"})
        backups = lock.get("backups", {})
        _restore_files(backups)
        _cleanup_backups(backups)
        lock = {"status": "unlocked", "holder": None, "timestamp": None, "backups": {}}
        _save_lock(lock)
        return json.dumps({"status": "rolled_back", "message": "Soul mutation rolled back. Files restored."})
    
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
