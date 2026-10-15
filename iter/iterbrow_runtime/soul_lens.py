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
