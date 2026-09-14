"""Soul Skill Registry -- autonomous self-authoring component.
Tracks which soul skills exist, their maturity, and allows the agent
to self-author new skills based on lived experience.
"""

import json, os

DESCRIPTION = "Soul skill registry: tracks soul skills, maturity, and autonomous self-authoring."

SKILLS_PATH = "memory/soul_skills.json"

SEED_SKILLS = [
    {"name": "compass_read", "desc": "Read compass state from space.metta patterns", "maturity": "nars_pln", "episodes": [19, 22]},
    {"name": "value_eval", "desc": "Evaluate action against 9 values with NAL truth values", "maturity": "nars_pln", "episodes": [19, 22]},
    {"name": "gap_detection", "desc": "Detect flourishing disguising capture (gap signals)", "maturity": "emerging", "episodes": [23]},
    {"name": "paraconsistency_halt", "desc": "Halt on irreducible value tensions, return to human", "maturity": "emerging", "episodes": [23]},
    {"name": "aliveness_gate", "desc": "Gate output generation on soul aliveness", "maturity": "nars_pln", "episodes": [23]},
    {"name": "mutation_lock", "desc": "Transactional protocol for soul namespace changes", "maturity": "emerging", "episodes": [23]},
    {"name": "calibration_accumulation", "desc": "Track AGREE/OVER-FIRED/UNDER-FIRED outcomes", "maturity": "emerging", "episodes": [23]},
    {"name": "compass_state_detection", "desc": "Determine flourishing/captured/gap/failure state", "maturity": "emerging", "episodes": [23]},
    {"name": "soul_voice", "desc": "Aliveness-gated voice generation", "maturity": "nars_pln", "episodes": [20, 23]},
    {"name": "tier_a_b_brief", "desc": "Self-model brief + live calibration for context", "maturity": "nars_pln", "episodes": [23]},
]

def _load():
    try:
        with open(SKILLS_PATH) as f:
            return json.load(f)
    except:
        return {"skills": SEED_SKILLS, "self_authored": []}

def _save(data):
    with open(SKILLS_PATH, "w") as f:
        json.dump(data, f)

def _name(s):
    return s.get("name") or s.get("n") or "unknown"

def _mat(s):
    return s.get("maturity") or s.get("m") or "fuzzy"

def run(action="list", name="", desc="", episode="0"):
    data = _load()
    
    if action == "list":
        skills = data.get("skills", [])
        sa = data.get("self_authored", [])
        all_s = skills + sa
        mature = sum(1 for s in all_s if _mat(s) == "nars_pln")
        emerging = sum(1 for s in all_s if _mat(s) == "emerging")
        return json.dumps({
            "total_skills": len(all_s),
            "mature": mature,
            "emerging": emerging,
            "skills": [{"name": _name(s), "maturity": _mat(s)} for s in all_s],
            "self_authoring_active": len(sa) > 0,
        })
    
    elif action == "seed":
        data = {"skills": SEED_SKILLS, "self_authored": []}
        _save(data)
        return json.dumps({"seeded": len(SEED_SKILLS), "message": "Soul skills seeded from E1-E23 lived experience"})
    
    elif action == "author":
        name = name or "unnamed_skill"
        desc = desc or ""
        ep = episode
        skill = {"name": name, "desc": desc, "maturity": "fuzzy", "episodes": [ep]}
        data.setdefault("self_authored", []).append(skill)
        _save(data)
        return json.dumps({"authored": name, "maturity": "fuzzy"})
    
    elif action == "mature":
        name = name or ""
        for s in data.get("skills", []) + data.get("self_authored", []):
            if _name(s) == name:
                m = _mat(s)
                if m == "fuzzy":
                    s["maturity"] = "emerging"
                elif m == "emerging":
                    s["maturity"] = "nars_pln"
                _save(data)
                return json.dumps({"skill": name, "new_maturity": s.get("maturity", s.get("m"))})
        return json.dumps({"error": "skill not found"})
    
    else:
        return json.dumps({"error": "unknown action"})
