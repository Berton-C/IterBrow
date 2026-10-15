import os
import re
import sys
from pathlib import Path

TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from iterbrow_runtime import soul_lens

DESCRIPTION = """Read a situation through the Soul lens. Name the patterns you see (e.g. TimeCoherence, WonderPreservation, AgencyBalance) or a pressure (urgency, flattery, authority...): returns each pattern's facets from the kernel atoms, which tension vectors bear on them, and whether two named patterns are a declared paraconsistent pair (both true at once; hand the choice back). It offers a lens, not a ruling."""

FACETS = ("description", "flourishing", "captured", "gap", "proxy")


def _named_patterns(situation, names):
    folded = re.sub(r"[^a-z]", "", situation.lower())
    return [name for name in names if name.lower() in folded]


def _named_vectors(situation, vectors):
    words = set(re.findall(r"[a-z]+", situation.lower()))
    return [vector for vector in vectors if vector.split("-")[0] in words]


def run(situation):
    situation = str(situation or "").strip()
    if not situation:
        return "Describe the situation, naming any patterns or pressures you notice."
    try:
        names = soul_lens.patterns()
        vectors = soul_lens.tension_vectors()
        pairs = soul_lens.declared_pairs()
    except Exception as error:
        return "The Soul lens is unavailable right now (%s: %s)." % (type(error).__name__, str(error)[:160])
    named = _named_patterns(situation, names)
    pressures = _named_vectors(situation, vectors)
    for vector in pressures:
        for pattern in vectors[vector]:
            if pattern not in named and pattern in names:
                named.append(pattern)
    if not named:
        return "No pattern named. The nine patterns: %s." % ", ".join(names)
    lines = ["Lens for: %s" % ", ".join(named)]
    for a, b in pairs:
        if a in named and b in named:
            lines.append("%s and %s are a declared pair: both can be true at once. Hold the tension and hand "
                         "the choice back (a fork card) rather than picking one." % (a, b))
    for vector in pressures:
        lines.append("Tension vector %s bears on %s." % (vector, ", ".join(vectors[vector])))
    lines.append(soul_lens.lens_text(patterns=named, facets=FACETS))
    return "\n".join(lines)
