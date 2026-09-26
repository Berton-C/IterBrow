"""Existing self_improve fitness arithmetic, shared with external recovery.

These are the original coarse measurements, not proof that an app works. Moving
their calculation here lets full_loop finish after the changed code has run,
without importing candidate code into the supervisor.
"""

import hashlib
import json
import time
from pathlib import Path

from tools._memory_projection import projection_chars


WEIGHTS = {"reliability": 0.4, "memory_efficiency": 0.3, "context_utilization": 0.3}


def _read(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def fitness_snapshot(iter_root, max_memory_chars=20000):
    root = Path(iter_root)
    reliability = _read(root / "transformations/.runtime/tool_reliability.json", {})
    scores = [data.get("f", 1.0) * data.get("c", 0.0)
              for data in reliability.values() if data.get("calls", 0) >= 2]
    snap = {
        "reliability": sum(scores) / len(scores) if scores else 0.5,
        "memory_efficiency": max(0.0, min(1.0, 1.0 -
            projection_chars(str(root / "memory")) / (max_memory_chars * 3))),
        "context_utilization": 0.5,
    }
    snap["composite"] = sum(WEIGHTS[key] * snap[key] for key in WEIGHTS)
    snap["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    return snap


def fitness_compare(prev, curr):
    if not prev or not curr:
        return {"delta_composite": 0.0, "delta_dimensions": {}, "effect": "unknown"}
    delta = curr.get("composite", 0.0) - prev.get("composite", 0.0)
    effect_size = abs(delta) / 0.5
    effect = ("negligible" if effect_size < 0.2 else "small" if effect_size < 0.5
              else "medium" if effect_size < 0.8 else "large")
    return {"delta_composite": delta,
            "delta_dimensions": {key: curr.get(key, 0.0) - prev.get(key, 0.0)
                                 for key in WEIGHTS},
            "effect": effect, "effect_size": effect_size}


def record_outcome(iter_root, generation, candidate, outcome, write_json):
    """Reuse the existing experiment/champion files; candidate IDs deduplicate."""
    root = Path(iter_root)
    result = candidate["fitness_result"]
    current = result["post_snapshot"]
    comparison = result["comparison"]
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (Path(generation) / "tools").glob("*.py")
              if not path.name.startswith("_")}
    entry = {
        "candidate_id": candidate["candidate_id"], "timestamp": current["timestamp"],
        "description": candidate["contract"]["purpose"],
        "files_changed": candidate["contract"]["allowed_writes"],
        "pre_composite": candidate["fitness_before"]["composite"],
        "post_composite": current["composite"],
        "delta_composite": comparison["delta_composite"],
        "effect": comparison["effect"], "outcome": outcome,
        "backup": "generation:" + candidate["parent_generation_id"],
        "file_hashes": hashes,
    }
    log_path = root / "memory/self_improve_log.json"
    log = _read(log_path, [])
    if not isinstance(log, list):
        log = []
    if not any(item.get("candidate_id") == entry["candidate_id"] for item in log):
        log.append(entry)
        write_json(log_path, log[-80:] if len(log) > 100 else log)
    if outcome != "accepted" or comparison["delta_composite"] < 0:
        return
    champion_path = root / "memory/champion.json"
    champion = _read(champion_path, {})
    for old, new in (("bc", "best_composite"), ("at", "set_at"), ("by", "set_by")):
        if old in champion and new not in champion:
            champion[new] = champion.pop(old)
    if current["composite"] > champion.get("best_composite", 0.0):
        champion.update(best_composite=current["composite"],
                        best_per_dimension={key: current[key] for key in WEIGHTS},
                        file_hashes=hashes, set_at=current["timestamp"],
                        set_by="self_improve")
        champion.setdefault("history", []).append({
            "candidate_id": candidate["candidate_id"], "timestamp": current["timestamp"],
            "composite": current["composite"],
            "delta": comparison["delta_composite"], "description": entry["description"],
        })
        write_json(champion_path, champion)
