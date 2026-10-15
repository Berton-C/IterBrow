"""Soul settings, per person (docs/milestones/M6_soul_base.md section B).

File: <ITER_DIR>/.runtime/soul_settings.json, written by main.js (sidebar Soul panel).
This module only reads it; a missing or damaged file means defaults, and reading never
writes. Every value is validated on the way out, so a hand-edited file cannot make a
feature half-on or a budget negative.
"""
import copy
import json
import os
from pathlib import Path

FEATURES = ("forks", "brief", "read", "wonder", "felt", "browsing_ally", "margin")
DEFAULT_FEATURES = {"forks": True, "brief": True, "read": False, "wonder": False,
                    "felt": False, "browsing_ally": False, "margin": False}
FREQUENCIES = ("whisper", "occasional", "chatty")
TONES = ("warm", "plain", "playful")
DEFAULT_PERSON = "guest"
DEFAULT_PROFILE = {"features": dict(DEFAULT_FEATURES), "frequency": "occasional", "tone": "warm",
                   "budget_per_cycle": 1}
MAX_BUDGET = 8


def settings_path():
    root = os.environ.get("ITER_DIR") or os.getcwd()
    return Path(root).resolve() / ".runtime" / "soul_settings.json"


def _read():
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _clean_profile(raw):
    profile = copy.deepcopy(DEFAULT_PROFILE)
    if not isinstance(raw, dict):
        return profile
    features = raw.get("features")
    if isinstance(features, dict):
        for name in FEATURES:
            if isinstance(features.get(name), bool):
                profile["features"][name] = features[name]
    if raw.get("frequency") in FREQUENCIES:
        profile["frequency"] = raw["frequency"]
    if raw.get("tone") in TONES:
        profile["tone"] = raw["tone"]
    budget = raw.get("budget_per_cycle")
    if isinstance(budget, int) and not isinstance(budget, bool) and 0 <= budget <= MAX_BUDGET:
        profile["budget_per_cycle"] = budget
    return profile


def _clean_person(value):
    if isinstance(value, str) and value.strip():
        name = value.strip().lower()
        if name.replace("_", "").replace("-", "").isalnum() and len(name) <= 40:
            return name
    return DEFAULT_PERSON


def load():
    """The whole settings document, cleaned: {schema_version, person, people{...}}."""
    data = _read()
    people = data.get("people") if isinstance(data.get("people"), dict) else {}
    return {
        "schema_version": 1,
        "person": _clean_person(data.get("person")),
        "people": {_clean_person(name): _clean_profile(profile) for name, profile in people.items()},
    }


def person():
    return load()["person"]


def for_person(name):
    """A person's profile; an unknown person gets the defaults."""
    return copy.deepcopy(load()["people"].get(_clean_person(name), DEFAULT_PROFILE))


def current():
    return for_person(person())


def enabled(feature):
    return bool(current()["features"].get(feature, False))


def enabled_features():
    profile = current()
    return [name for name in FEATURES if profile["features"].get(name)]


def frequency():
    return current()["frequency"]


def tone():
    return current()["tone"]


def budget():
    return current()["budget_per_cycle"]
