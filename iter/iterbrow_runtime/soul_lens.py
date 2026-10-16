"""The Soul lens: pattern text for a prompt, read from the kernel atoms.

docs/milestones/M6_soul_base.md section C. This is the ONLY place pattern text enters
Python: it asks the AtomSpace "soul" view for the facet atoms of seeds/soul_kernel.metta,
so a prompt can never drift from the seed. Nothing here decides anything; it renders
the lens Iter looks through.
"""
import re

FACETS = {
    "description": "soul-pattern", "flourishing": "soul-pattern-pole+", "captured": "soul-pattern-pole-",
    "signal": "soul-pattern-signal", "felt": "soul-pattern-felt", "moat": "soul-pattern-moat",
    "anti": "soul-pattern-anti", "proxy": "soul-pattern-proxy", "gap": "soul-pattern-gap",
}
LABELS = {"description": "", "flourishing": "Flourishing", "captured": "Captured", "signal": "Signal",
          "felt": "Felt", "moat": "Moat", "anti": "Failure mode", "proxy": "Proxy", "gap": "Gap"}
_PAIR = re.compile(r'\(lens (\S+) "((?:[^"\\]|\\.)*)"\)')


def soul_query(code, timeout=60):
    from iterbrow_runtime.cognitive_events import _call_atomspace
    return _call_atomspace("query", timeout=timeout, code=code, view="soul")["result"]


def facet(name, query=soul_query):
    """{pattern: text} for one facet."""
    head = FACETS[name]
    text = query("!(match &self (%s $p $d) (lens $p $d))" % head)
    return {pattern: value for pattern, value in _PAIR.findall(text)}


def patterns(query=soul_query):
    """Pattern names in seed order."""
    return list(facet("description", query))


def declared_pairs(query=soul_query):
    text = query("!(match &self (soul-paraconsistent-pair $a $b) (pair $a $b))")
    return re.findall(r"\(pair (\S+) (\S+)\)", text)


def tension_vectors(query=soul_query):
    """{vector: [patterns it threatens]}"""
    vectors = {name: [] for name in re.findall(r"\(tv (\S+)\)", query("!(match &self (tension-vector $t) (tv $t))"))}
    for vector, pattern in re.findall(r"\(th (\S+) (\S+)\)", query("!(match &self (threatens $t $p) (th $t $p))")):
        vectors.setdefault(vector, []).append(pattern)
    return vectors


def lens_text(patterns=None, facets=("description", "gap"), query=soul_query):
    """Prose for a prompt: each pattern with the requested facets (default: what it holds
    and its gap signature, where flourishing and capture look alike)."""
    wanted = None if patterns is None else set(patterns)
    texts = {name: facet(name, query) for name in facets}
    order = list(texts[facets[0]]) if facets else []
    lines = []
    for pattern in order:
        if wanted is not None and pattern not in wanted:
            continue
        parts = []
        for name in facets:
            value = texts[name].get(pattern)
            if value:
                parts.append(("%s: %s" % (LABELS[name], value)) if LABELS[name] else value)
        lines.append("- %s — %s" % (pattern, " ".join(parts)))
    return "\n".join(lines)


# ---- Taste: what the Soul has learned from a person's card answers --------
# docs/milestones/M7_soul_personality.md section A. The atoms are written by
# transformations/soul_taste.py; these readers use read_atoms (exact, no MeTTa
# evaluation), or a {key: atom} dict the caller already holds (the dashboard).
LEAN_MIN_FORKS = 2
LEAN_MIN_F = 0.67
DISMISS_MIN = 3
_TASTE = re.compile(r'^\(soul-taste "((?:[^"\\]|\\.)*)" (\S+) (\S+) \(stv ([0-9.]+) ([0-9.]+)\) (\d+)\)$')
_DISMISS = re.compile(r'^\(soul-dismissed "((?:[^"\\]|\\.)*)" "((?:[^"\\]|\\.)*)" (\d+)\)$')
_CHOICE = re.compile(r'^\(soul-choice "((?:[^"\\]|\\.)*)" "((?:[^"\\]|\\.)*)" "((?:[^"\\]|\\.)*)" "((?:[^"\\]|\\.)*)" (\d+)\)$')


def read_atoms(prefix):
    from iterbrow_runtime.cognitive_events import _call_atomspace
    return _call_atomspace("read_atoms", prefix=prefix)["atoms"]


def _atoms(prefix, atoms):
    if atoms is None:
        return read_atoms(prefix)
    return {key: atom for key, atom in atoms.items() if key.startswith(prefix)}


def taste(person, atoms=None):
    """[{picked, over, f, c, n}] for one person, most confident first."""
    out = []
    for atom in _atoms("state:soul_taste:%s:" % person, atoms).values():
        match = _TASTE.match(atom.strip())
        if match and match.group(1) == person:
            out.append({"picked": match.group(2), "over": match.group(3), "f": float(match.group(4)),
                        "c": float(match.group(5)), "n": int(match.group(6))})
    out.sort(key=lambda t: (t["c"], t["f"]), reverse=True)
    return out


def dismissals(person, atoms=None):
    """{card kind: times dismissed} for one person."""
    out = {}
    for atom in _atoms("state:soul_dismiss:%s:" % person, atoms).values():
        match = _DISMISS.match(atom.strip())
        if match and match.group(1) == person:
            out[match.group(2)] = int(match.group(3))
    return out


def answered(person, atoms=None):
    """{card kind: cards answered (not dismissed)} for one person."""
    out = {}
    for atom in _atoms("state:soul_choice:", atoms).values():
        match = _CHOICE.match(atom.strip())
        if match and match.group(1) == person and match.group(4) != "dismiss":
            out[match.group(2)] = out.get(match.group(2), 0) + 1
    return out


def taste_line(person, atoms=None):
    """One sentence of what the Soul has learned about `person`, or ""."""
    parts = []
    for lean in taste(person, atoms):
        if lean["n"] >= LEAN_MIN_FORKS and lean["f"] >= LEAN_MIN_F:
            parts.append("you've leaned %s over %s (%d of %d forks)"
                         % (lean["picked"], lean["over"], round(lean["f"] * lean["n"]), lean["n"]))
        if len(parts) == 2:
            break
    dismissed = dismissals(person, atoms)
    if dismissed:
        kept = answered(person, atoms)
        for kind in sorted(dismissed):
            if dismissed[kind] >= DISMISS_MIN and dismissed[kind] > kept.get(kind, 0):
                parts.append("you dismiss most %s cards" % kind)
    return "; ".join(parts)
