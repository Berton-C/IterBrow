#!/usr/bin/env python3
"""Port the ClarityOmega Soul kernel atoms into IterBrow's seeds/soul_kernel.metta.

docs/milestones/M6_soul_base.md section C. Reads the reference soul/soul_kernel.metta,
keeps ONLY the value atoms (priorities, the nine patterns x nine facets, relations,
paraconsistent pairs, tension vectors, will thresholds, autonomy components, causal
atoms) and the read-only accessor functions over them, verbatim. Gates, operation risk,
file classes, mutation and output governance are NOT ported (IterBrow has no gates).

Usage: scripts/port_soul_kernel.py <path/to/clarityomega/soul/soul_kernel.metta> [out]
"""
import re
import sys
from pathlib import Path

KEEP_HEADS = ("priority", "soul-pattern", "soul-pattern-pole+", "soul-pattern-pole-", "soul-pattern-signal",
              "soul-pattern-felt", "soul-pattern-moat", "soul-pattern-anti", "soul-pattern-proxy", "soul-pattern-gap",
              "soul-pattern-related", "soul-pattern-degrades-without", "soul-paraconsistent-pair", "tension-vector",
              "threatens", "soul-will-threshold", "soul-autonomy-component", "soul-causal")
KEEP_FUNCTIONS = ("soul-priority-hierarchy", "soul-all-patterns", "soul-pattern-description", "soul-pattern-relations",
                  "soul-related-patterns", "soul-all-tensions", "soul-all-affinities", "soul-patterns-at-risk",
                  "soul-pattern-flourishing", "soul-pattern-captured", "soul-pattern-activation-signal",
                  "soul-pattern-doorway", "soul-pattern-suck-moat", "soul-pattern-failure-mode",
                  "soul-pattern-proxy-signal", "soul-pattern-gap-signature", "soul-all-gap-signatures",
                  "soul-pattern-needs", "soul-all-degradation-pairs", "soul-will-threshold-for",
                  "soul-paraconsistent-pairs", "soul-autonomy-components", "soul-causal-procedures",
                  "soul-values-for-procedure", "soul-rationality-check")


def units(text):
    """Balanced top-level expressions, with comments stripped outside strings."""
    out, depth, start, in_string, escape, i = [], 0, None, False, False, 0
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        elif ch == ";":
            i = text.find("\n", i)
            if i < 0:
                break
            continue
        elif ch == '"':
            in_string = True
        elif ch == "(":
            if depth == 0:
                start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and start is not None:
                out.append(text[start:i + 1])
                start = None
        i += 1
    return out


def head(expr):
    match = re.match(r"\(\s*([^\s()]+)", expr)
    return match.group(1) if match else ""


def port(reference_text):
    atoms, functions = [], []
    for unit in units(reference_text):
        body = unit
        bang = re.match(r"\(\s*add-atom\s+&self\s+", unit)
        if bang:
            body = unit[bang.end():unit.rstrip().rfind(")")].strip()
            if head(body) in KEEP_HEADS:
                atoms.append(body)
            continue
        if head(unit) == "=":
            name = re.match(r"\(=\s*\(\s*([^\s()]+)", unit)
            if name and name.group(1) in KEEP_FUNCTIONS:
                functions.append(unit)
    return atoms, functions


HEADER = ''';; Soul kernel — the value atoms of the ClarityOmega Soul, ported verbatim
;; (docs/milestones/M6_soul_base.md section C; generator: scripts/port_soul_kernel.py).
;; Source: Berton-C/ClarityOmega soul/soul_kernel.metta.
;;
;; Loaded ONLY in the AtomSpace "soul" query view, never with NACE or kb atoms.
;; These atoms are a lens Iter reads through, not rules that decide anything:
;; IterBrow has no gates. The priority hierarchy is declared for fidelity and is
;; not used for routing. Paraconsistent pairs are genuine tensions that cannot be
;; collapsed to a winner; when both values are live, the choice goes back to the
;; person (in IterBrow: a fork card).

'''

PAIR_PREDICATE = '''
;; True when $a and $b are a declared paraconsistent pair (either order).
(= (soul-paraconsistent? $a $b)
   (if (== () (collapse (match &self (soul-paraconsistent-pair $a $b) True)))
       (if (== () (collapse (match &self (soul-paraconsistent-pair $b $a) True))) False True)
       True))
'''


def render(atoms, functions):
    return (HEADER + ";; ---- atoms ----\n" + "\n".join(atoms) + "\n\n;; ---- read-only accessors (verbatim) ----\n"
            + "\n".join(functions) + "\n" + PAIR_PREDICATE)


if __name__ == "__main__":
    source = Path(sys.argv[1]).read_text(encoding="utf-8")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / "iter" / "seeds" / "soul_kernel.metta"
    atoms, functions = port(source)
    out.write_text(render(atoms, functions), encoding="utf-8")
    print("wrote %s: %d atoms, %d accessors" % (out, len(atoms), len(functions)))
