"""Bounded forward chaining over knowledge-base statements (Milestone 5, section D).

Rules live in seeds/kb_inference.metta (kb-step-mp, kb-step-chain) and run in
the isolated Hyperon query path against the committed `(kb ...)` atoms.  Each
round adds the previous rounds' derivations as program-local facts, so round k
finds what is reachable in k steps.  Derivations are returned, never written.
"""
import os
import time

from iterbrow_runtime import kb_terms

MAX_DEPTH = 3
DEFAULT_BUDGET_S = 5.0
STORED_QUERY = "!(match &self (kb $s $t) (stored $s $t))"
STEP_QUERIES = "!(kb-step-mp)\n!(kb-step-chain)"


class Derivations(list):
    """A list of derivation dicts that also says whether it was cut short."""

    def __init__(self, items=(), truncated=False):
        super().__init__(items)
        self.truncated = truncated


def service_query(code, timeout=60):
    """Evaluate MeTTa in the AtomSpace service's isolated query path (current view)."""
    from iterbrow_runtime.cognitive_events import _call_atomspace
    return _call_atomspace("query", timeout=timeout, code=code, view="current")["result"]


def _stv(tree):
    if not (isinstance(tree, list) and len(tree) == 3 and tree[0] == "stv"):
        raise ValueError("not an stv: %r" % (tree,))
    return (round(float(tree[1]), 6), round(float(tree[2]), 6))


def _canonical(tree):
    return kb_terms.serialize(kb_terms._canonical_tree(tree)[0])


def _generalizes(general, specific, bindings):
    """One-way match: `general`'s variables bind to subtrees of `specific`."""
    if isinstance(general, str) and general.startswith("$"):
        if general in bindings:
            return bindings[general] == specific
        bindings[general] = specific
        return True
    if isinstance(general, list):
        if not isinstance(specific, list) or len(general) != len(specific):
            return False
        return all(_generalizes(g, s, bindings) for g, s in zip(general, specific))
    return general == specific


def _premise(tree, known_trees):
    """The known statement an instantiated premise came from (Hyperon prints premises bound)."""
    text = _canonical(tree)
    if text in known_trees:
        return text
    candidates = [(statement.count("$"), statement) for statement, general in known_trees.items()
                  if _generalizes(general, kb_terms.parse_sexpr(text), {})]
    return min(candidates)[1] if candidates else text


def derive(run_query, depth=2, limit=64, budget_s=None):
    """Derivations reachable in at most `depth` (<= 3) steps; see module docstring.

    run_query(code) -> result text.  Engine errors propagate.
    """
    depth = max(1, min(int(depth), MAX_DEPTH))
    if budget_s is None:
        try:
            budget_s = float(os.environ.get("ITER_KB_DERIVE_BUDGET_S", DEFAULT_BUDGET_S))
        except ValueError:
            budget_s = DEFAULT_BUDGET_S
    started = time.monotonic()
    stored = {}
    derived = {}
    truncated = False
    for round_number in range(1, depth + 1):
        facts = "\n".join(kb_terms.statement_atom(statement, item["stv"])
                          for statement, item in sorted(derived.items()))
        code = "\n".join(part for part in (
            facts, STORED_QUERY if round_number == 1 else "", STEP_QUERIES) if part)
        text = run_query(code)
        if round_number == 1:
            for tree in kb_terms.find_sexprs(text, "stored"):
                stored[_canonical(tree[1])] = _stv(tree[2])
        known_trees = {statement: kb_terms.parse_sexpr(statement) for statement in list(stored) + list(derived)}
        found_new = False
        for tree in kb_terms.find_sexprs(text, "derived"):
            if len(tree) != 5:
                continue
            statement = _canonical(tree[1])
            if statement in stored:
                continue
            stv = _stv(tree[2])
            premises = [_premise(tree[3], known_trees), _premise(tree[4], known_trees)]
            previous = derived.get(statement)
            if previous is not None and previous["stv"][1] >= stv[1]:
                continue
            sources = set()
            for premise in premises:
                if premise in derived:
                    sources |= set(derived[premise]["sources"])
                else:
                    sources.add(premise)
            derived[statement] = {
                "statement": statement, "stv": stv, "premises": premises,
                "depth": previous["depth"] if previous else round_number,
                "sources": sorted(sources),
            }
            found_new = found_new or previous is None
        if not found_new:
            break
        if round_number < depth and time.monotonic() - started >= budget_s:
            truncated = True
            break
    items = sorted(derived.values(), key=lambda d: (d["depth"], -d["stv"][1], d["statement"]))
    if len(items) > limit:
        items, truncated = items[:limit], True
    return Derivations(items, truncated)


def stored_statements(read_atoms):
    """{statement: ((f, c), [evidence memory ids])} from the authority."""
    atoms = read_atoms(kb_terms.KB_PREFIX)
    evidence = {}
    for key in atoms:
        if key.startswith(kb_terms.EVIDENCE_PREFIX):
            digest, memory_id = kb_terms.parse_evidence_key(key)
            evidence.setdefault(digest, []).append(memory_id)
    out = {}
    for key, atom in atoms.items():
        if not key.startswith(kb_terms.STATEMENT_PREFIX):
            continue
        try:
            statement, stv = kb_terms.parse_statement_atom(atom)
        except ValueError:
            continue
        out[statement] = (stv, sorted(evidence.get(key[len(kb_terms.STATEMENT_PREFIX):], [])))
    return out


def unifies(pattern, statement):
    """Two-way unification (separate variable namespaces) of a pattern and a statement."""
    left = _rename(kb_terms.parse_sexpr(pattern), "l")
    right = _rename(kb_terms.parse_sexpr(statement), "r")
    return _unify(left, right, {}) is not None


def _rename(tree, tag):
    if isinstance(tree, list):
        return [_rename(item, tag) for item in tree]
    return tree + "#" + tag if tree.startswith("$") else tree


def _walk(term, bindings):
    while isinstance(term, str) and term.startswith("$") and term in bindings:
        term = bindings[term]
    return term


def _unify(a, b, bindings):
    a, b = _walk(a, bindings), _walk(b, bindings)
    if a == b:
        return bindings
    if isinstance(a, str) and a.startswith("$"):
        return dict(bindings, **{a: b})
    if isinstance(b, str) and b.startswith("$"):
        return dict(bindings, **{b: a})
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for x, y in zip(a, b):
            bindings = _unify(x, y, bindings)
            if bindings is None:
                return None
        return bindings
    return None


def format_derivation(item):
    return "[derived] %s %s ⇐ %s" % (item["statement"], kb_terms.stv_text(item["stv"]), ", ".join(item["premises"]))
