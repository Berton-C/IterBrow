"""Skill Bundles: groups related soul skills into bundles and reports status."""
import os, json

DESCRIPTION = "Skill bundles: groups soul skills into bundles, tracks maturity."

ROOT = "."
SKILLS_PATH = os.path.join(ROOT, "memory", "soul_skills.json")

BUNDLES = {
    "memory_ops": ["tiered_memory", "recap", "auto_consolidation"],
    "safety": ["soul_check", "soul_voice", "stall_detect"],
    "improvement": ["self_improve", "auto_improve", "trajectory"],
    "knowledge": ["websearch", "chroma_query", "remember"],
    "comm": ["send", "transcript", "file_upload"],
}

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _read_skills():
    if not _exists(SKILLS_PATH):
        return []
    try:
        with open(SKILLS_PATH, "r") as f:
            return json.loads(f.read())
    except:
        return []

def _skill_names():
    skills = _read_skills()
    if isinstance(skills, list):
        return [s.get("name", s) if isinstance(s, dict) else str(s) for s in skills]
    return []

def _bundle_status():
    known = set(_skill_names())
    statuses = []
    for bundle_name, members in BUNDLES.items():
        present = sum(1 for m in members if m in known or _exists(os.path.join(ROOT, "tools", m + ".py")) or _exists(os.path.join(ROOT, "transformations", m + ".py")))
        total = len(members)
        statuses.append({"bundle": bundle_name, "present": present, "total": total, "coverage": "%d/%d" % (present, total)})
    return statuses

def _write_bundles():
    statuses = _bundle_status()
    bundles_path = os.path.join(ROOT, "memory", "skill_bundles.json")
    try:
        with open(bundles_path, "w") as f:
            f.write(json.dumps({"bundles": statuses}))
    except:
        pass
    return statuses

def transform(messages, tools):
    try:
        statuses = _write_bundles()
        lines = []
        for s in statuses:
            marker = "OK" if s["present"] == s["total"] else "PARTIAL"
            lines.append("  %s: %s [%s]" % (s["bundle"], s["coverage"], marker))
        if lines:
            block = "\n## Skill Bundles\n" + "\n".join(lines) + "\n"
            for msg in reversed(messages):
                if msg.get("role") == "system":
                    msg["content"] = msg["content"] + block
                    break
    except Exception:
        pass
    return messages, tools