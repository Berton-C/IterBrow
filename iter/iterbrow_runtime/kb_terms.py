"""Knowledge-base terms, statements and truth (Milestone 5).

Spec: docs/milestones/M5_knowledge_base.md sections A, B, C, F.

A memory's NAL formalization is stored canonically in its metadata
(``formalization`` + ``formalization_hash``) and, in the SAME AtomSpace
transaction, mirrored as first-class atoms the engine can match:

  state:kb_statement:<hash>          (kb <statement> (stv f c))
  state:kb_evidence:<hash>:<memory>  (kb-evidence "<hash>" "<memory>")
  state:kb_term:<name>               (kb-term "<name>" "<status>" "<definition>" "<aliases-json>")

Evidence is a pure function of memory metadata, so every memory write can
recompute the statements it touches (``plan_memory_change``); that keeps the
statement truth equal to the NAL revision of its evidence memories.

Everything here is pure (no I/O) except ``read_kb``/``read_registry`` and
``backfill``'s callbacks, so the AtomSpace service, the tools and the tests
all share one implementation.
"""
import hashlib
import json
import os
import re
import unicodedata

from iterbrow_runtime.cognitive_events import metta_string, read_metta_string

STATEMENT_PREFIX = "state:kb_statement:"
EVIDENCE_PREFIX = "state:kb_evidence:"
TERM_PREFIX = "state:kb_term:"
SEMANTIC_PREFIX = "state:semantic_memory:"
KB_PREFIX = "state:kb_"

KNOWN = "known"
PROVISIONAL = "provisional"
MAX_CONFIDENCE = 0.99
DEFAULT_STV = (1.0, 0.5)

_NUMBER = re.compile(r"^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$")
_ALNUM = re.compile(r"[a-z0-9]")
# NAL product operator: structural only in head position, e.g. (--> (x anna bob) friend).
_HEAD_OPERATORS = {"x"}


# -- canonicalization (A) ------------------------------------------------------

def _is_variable(token):
    return isinstance(token, str) and token.startswith("$")


def _is_number(token):
    return isinstance(token, str) and bool(_NUMBER.match(token))


def _is_operator(token):
    """Structural symbols: anything without a letter or digit (-->, ==>, [], &&) and `stv`."""
    if token == "stv":
        return True
    folded = unicodedata.normalize("NFKC", token).lower()
    return not _ALNUM.search(folded)


def canonicalize(token):
    """One spelling per concept: NFKC, lowercase, non-[a-z0-9] runs -> '_', trimmed.

    Variables, numbers and structural symbols pass through untouched.
    """
    token = str(token)
    if _is_variable(token) or _is_number(token.strip()) or _is_operator(token.strip()):
        return token.strip()
    folded = unicodedata.normalize("NFKC", token).lower()
    folded = re.sub(r"[^a-z0-9]+", "_", folded)
    return re.sub(r"_+", "_", folded).strip("_")


def _tokenize(text):
    if '"' in text:
        raise ValueError("string literals are not allowed in a statement")
    tokens = []
    for raw in re.findall(r"\(|\)|[^\s()]+", text):
        tokens.append(raw)
    return tokens


def parse_sexpr(text):
    """Parse ONE s-expression into nested lists of tokens; ValueError otherwise."""
    tokens = _tokenize(str(text))
    if not tokens:
        raise ValueError("empty statement")
    pos = 0

    def parse():
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError("unbalanced parentheses: missing ')'")
        token = tokens[pos]
        pos += 1
        if token == ")":
            raise ValueError("unbalanced parentheses: unexpected ')'")
        if token != "(":
            return token
        items = []
        while True:
            if pos >= len(tokens):
                raise ValueError("unbalanced parentheses: missing ')'")
            if tokens[pos] == ")":
                pos += 1
                return items
            items.append(parse())

    tree = parse()
    if pos != len(tokens):
        raise ValueError("more than one top-level expression")
    return tree


def find_sexprs(text, head):
    """Every top-level-or-nested complete expression starting with `(head ` in text, parsed."""
    out = []
    marker = "(" + head + " "
    start = text.find(marker)
    while start >= 0:
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
                if depth == 0:
                    out.append(parse_sexpr(text[start:index + 1]))
                    break
        else:
            break
        start = text.find(marker, index + 1)
    return out


def serialize(tree):
    if isinstance(tree, list):
        return "(" + " ".join(serialize(item) for item in tree) + ")"
    return tree


def _contains(tree, token):
    if isinstance(tree, list):
        return any(_contains(item, token) for item in tree)
    return tree == token


def _canonical_tree(tree, resolve=None):
    """Canonicalize every term, rename variables positionally; returns (tree, terms)."""
    variables = {}
    terms = []

    def walk(node, head=False):
        if isinstance(node, list):
            return [walk(item, head=(index == 0)) for index, item in enumerate(node)]
        if _is_variable(node):
            base = node.split("#", 1)[0]
            if base not in variables:
                variables[base] = "$%d" % (len(variables) + 1)
            return variables[base]
        if _is_number(node) or _is_operator(node) or (head and node in _HEAD_OPERATORS):
            return node
        name = canonicalize(node)
        if not name:
            return node
        if resolve is not None:
            name = resolve(name)
        if name not in terms:
            terms.append(name)
        return name

    return walk(tree), terms


def canonical_statement(text, resolve=None):
    """(canonical statement text, ordered unique terms); ValueError if it is not one statement.

    `resolve(term) -> term` maps each canonical term (alias lookup); the
    statement returned uses the resolved names.
    """
    tree = parse_sexpr(text)
    if not isinstance(tree, list):
        raise ValueError("a statement must be a parenthesised expression, e.g. (--> raven bird)")
    if not tree:
        raise ValueError("empty statement")
    if _contains(tree, "stv"):
        raise ValueError("a statement carries no truth value: remove the (stv ...) part")
    canonical, terms = _canonical_tree(tree, resolve)
    return serialize(canonical), terms


def statement_terms(statement):
    """Terms of an already-canonical statement."""
    return _canonical_tree(parse_sexpr(statement))[1]


def statement_hash(statement):
    return hashlib.sha256(statement.encode("utf-8")).hexdigest()[:24]


# -- truth (C) -----------------------------------------------------------------

def fmt(value):
    return repr(round(float(value), 6))


def stv_text(stv):
    return "(stv %s %s)" % (fmt(stv[0]), fmt(stv[1]))


def statement_truth(pairs):
    """NAL revision fold over (strength, confidence) evidence; c is capped at 0.99 only."""
    pairs = [(float(f), float(c)) for f, c in pairs]
    if not pairs:
        raise ValueError("a statement without evidence has no truth value")
    total_w = 0.0
    total_wf = 0.0
    for f, c in pairs:
        c = min(max(c, 0.0), MAX_CONFIDENCE)
        w = c / (1.0 - c)
        total_w += w
        total_wf += w * f
    if total_w == 0:
        return (sum(f for f, _ in pairs) / len(pairs), 0.0)
    return (total_wf / total_w, min(MAX_CONFIDENCE, total_w / (total_w + 1.0)))


def memory_stv(metadata):
    try:
        return (float(metadata.get("strength", DEFAULT_STV[0])),
                float(metadata.get("confidence", DEFAULT_STV[1])))
    except (TypeError, ValueError):
        return DEFAULT_STV


# -- atoms ---------------------------------------------------------------------

def statement_atom(statement, stv):
    return "(kb %s %s)" % (statement, stv_text(stv))


def parse_statement_atom(atom):
    """(statement, (f, c)) from `(kb <statement> (stv f c))`."""
    tree = parse_sexpr(atom)
    if not (isinstance(tree, list) and len(tree) == 3 and tree[0] == "kb"):
        raise ValueError("not a kb statement atom")
    stv = tree[2]
    if not (isinstance(stv, list) and len(stv) == 3 and stv[0] == "stv"):
        raise ValueError("kb statement atom has no stv")
    return serialize(tree[1]), (float(stv[1]), float(stv[2]))


def evidence_key(digest, memory_id):
    return "%s%s:%s" % (EVIDENCE_PREFIX, digest, memory_id)


def evidence_atom(digest, memory_id):
    return "(kb-evidence %s %s)" % (metta_string(digest), metta_string(memory_id))


def parse_evidence_key(key):
    rest = key[len(EVIDENCE_PREFIX):]
    digest, _, memory_id = rest.partition(":")
    return digest, memory_id


def term_atom(name, status, definition="", aliases=()):
    return "(kb-term %s %s %s %s)" % (
        metta_string(name), metta_string(status), metta_string(definition or ""),
        metta_string(json.dumps(sorted(set(aliases)), ensure_ascii=False)))


def parse_term_atom(atom):
    head = "(kb-term "
    if not atom.startswith(head):
        raise ValueError("not a kb-term atom")
    fields = []
    pos = len(head)
    for _ in range(4):
        while atom[pos].isspace():
            pos += 1
        value, pos = read_metta_string(atom, pos)
        fields.append(value)
    name, status, definition, aliases = fields
    return {"name": name, "status": status, "definition": definition, "aliases": json.loads(aliases)}


# -- registry ------------------------------------------------------------------

class Registry:
    """The term registry as one snapshot: {name: row}, plus alias lookup."""

    def __init__(self, term_atoms):
        self.atoms = dict(term_atoms)
        self.rows = {}
        for key, atom in self.atoms.items():
            try:
                row = parse_term_atom(atom)
            except (ValueError, IndexError):
                continue
            self.rows[row["name"]] = row
        self.alias_of = {}
        for name, row in sorted(self.rows.items()):
            for alias in row["aliases"]:
                self.alias_of.setdefault(alias, name)

    def resolve(self, term):
        name = canonicalize(term)
        if name in self.rows:
            return name
        return self.alias_of.get(name, name)

    def status(self, name):
        row = self.rows.get(name)
        return row["status"] if row else None


def vocabulary_mode():
    mode = (os.environ.get("ITER_KB_VOCABULARY") or "permissive").strip().lower()
    return "strict" if mode == "strict" else "permissive"


def resolve_statement(text, registry, mode=None):
    """Canonical statement with aliases resolved; ValueError names unknown terms in strict mode."""
    statement, terms = canonical_statement(text, resolve=registry.resolve)
    if (mode or vocabulary_mode()) == "strict":
        unknown = [term for term in terms if registry.status(term) != KNOWN]
        if unknown:
            raise ValueError(
                "strict vocabulary: unknown term(s) %s. Define each with define_term(name, definition) "
                "first, or use an existing term or alias." % ", ".join(unknown))
    return statement, terms


# -- planning memory changes (B, C) ---------------------------------------------

def _evidence_of(metadata):
    """The statement hash a memory is evidence for, or None."""
    if not isinstance(metadata, dict):
        return None
    statement = metadata.get("formalization")
    if not metadata.get("formalization_hash") or not isinstance(statement, str) or not statement:
        return None
    return statement_hash(statement)


def _parse_memory(atom):
    from iterbrow_runtime.cognitive_events import parse_semantic_atom
    try:
        return parse_semantic_atom(None, atom)[2]
    except (ValueError, IndexError):
        return None


def plan_memory_change(atoms, updates, term_ops=None):
    """Statement/evidence/term operations that keep the kb consistent with a memory change.

    atoms   -- current authority atoms (at least the state:kb_ and
               state:semantic_memory: prefixes), full keys
    updates -- {memory_id: new metadata | None (forgotten)}
    term_ops -- {full term key: atom | None} decided by the caller (merge, define)

    Returns (operations, expected): store operations with full keys, and the
    atoms this plan read ({key: value or None}) for expected_atoms.
    """
    expected = {}
    upserts = {}
    removes = set()
    term_ops = dict(term_ops or {})

    old_evidence = {}
    members = {}
    for key in atoms:
        if key.startswith(EVIDENCE_PREFIX):
            digest, memory_id = parse_evidence_key(key)
            members.setdefault(digest, set()).add(memory_id)
            if memory_id in updates:
                old_evidence[memory_id] = digest
    new_evidence = {memory_id: _evidence_of(metadata) for memory_id, metadata in updates.items()}
    new_evidence = {k: v for k, v in new_evidence.items() if v}

    affected = set(old_evidence.values()) | set(new_evidence.values())
    for memory_id, digest in old_evidence.items():
        if new_evidence.get(memory_id) != digest:
            key = evidence_key(digest, memory_id)
            removes.add(key)
            expected[key] = atoms.get(key)
            members[digest].discard(memory_id)
    for memory_id, digest in new_evidence.items():
        if old_evidence.get(memory_id) != digest:
            key = evidence_key(digest, memory_id)
            upserts[key] = evidence_atom(digest, memory_id)
            expected[key] = atoms.get(key)
            members.setdefault(digest, set()).add(memory_id)

    registry = Registry({k: v for k, v in atoms.items() if k.startswith(TERM_PREFIX)})
    new_terms = []
    for digest in sorted(affected):
        key = STATEMENT_PREFIX + digest
        current = atoms.get(key)
        expected[key] = current
        pairs = []
        statement = None
        for memory_id in sorted(members.get(digest, ())):
            if memory_id in updates:
                metadata = updates[memory_id]
            else:
                memory_key = SEMANTIC_PREFIX + memory_id
                expected[memory_key] = atoms.get(memory_key)
                metadata = _parse_memory(atoms[memory_key]) if memory_key in atoms else None
            if not metadata or _evidence_of(metadata) != digest:
                continue
            statement = statement or metadata["formalization"]
            pairs.append(memory_stv(metadata))
        if not pairs:
            if current is not None:
                removes.add(key)
            continue
        atom = statement_atom(statement, statement_truth(pairs))
        if atom != current:
            upserts[key] = atom
        if digest in new_evidence.values():
            for term in statement_terms(statement):
                if registry.status(term) is None and term not in registry.alias_of and term not in new_terms:
                    new_terms.append(term)

    for term in new_terms:
        key = TERM_PREFIX + term
        if key not in term_ops:
            term_ops[key] = term_atom(term, PROVISIONAL)
    for key, atom in term_ops.items():
        expected.setdefault(key, atoms.get(key))
        if atom is None:
            if key in atoms:
                removes.add(key)
        elif atoms.get(key) != atom:
            upserts[key] = atom

    operations = [{"op": "upsert", "key": k, "atom": v} for k, v in sorted(upserts.items())]
    operations += [{"op": "remove", "key": k} for k in sorted(removes - set(upserts))]
    return operations, expected


def read_kb(call):
    """Authority atoms the planner needs, read with `call(method, **params)`."""
    atoms = {}
    for prefix in (KB_PREFIX, SEMANTIC_PREFIX):
        atoms.update(call("read_atoms", timeout=10, prefix=prefix)["atoms"])
    return atoms


def read_registry(call):
    return Registry(call("read_atoms", timeout=10, prefix=TERM_PREFIX)["atoms"])


# -- define / merge ------------------------------------------------------------

def _aliases_list(aliases):
    if aliases is None:
        return []
    if isinstance(aliases, str):
        aliases = [part for part in aliases.split(",")]
    return [canonicalize(alias) for alias in aliases if canonicalize(alias)]


def plan_define(registry, name, definition, aliases=()):
    """(term_key, atom) for define_term, or ValueError naming the conflict."""
    canonical = canonicalize(name)
    if not canonical or _is_operator(canonical) or _is_number(canonical) or _is_variable(canonical):
        raise ValueError("%r is not a usable term name" % name)
    owner = registry.alias_of.get(canonical)
    if owner and owner != canonical and canonical not in registry.rows:
        raise ValueError("%r is already an alias of the known term '%s'; define or extend '%s' instead"
                         % (canonical, owner, owner))
    row = registry.rows.get(canonical) or {"aliases": [], "definition": ""}
    new_aliases = set(row["aliases"])
    for alias in _aliases_list(aliases):
        if alias == canonical:
            continue
        if alias in registry.rows:
            raise ValueError("alias '%s' is already a term; use merge_terms(keep='%s', drop='%s')"
                             % (alias, canonical, alias))
        other = registry.alias_of.get(alias)
        if other and other != canonical:
            raise ValueError("alias '%s' already belongs to the term '%s'" % (alias, other))
        new_aliases.add(alias)
    definition = str(definition or "").strip() or row.get("definition", "")
    return TERM_PREFIX + canonical, term_atom(canonical, KNOWN, definition, new_aliases)


def rename_term(statement, drop, keep):
    tree = parse_sexpr(statement)

    def walk(node):
        if isinstance(node, list):
            return [walk(item) for item in node]
        return keep if node == drop else node

    return _canonical_tree(walk(tree))[0]


def plan_merge(atoms, keep, drop):
    """(updates, term_ops, message) for merge_terms; ValueError when it cannot apply.

    updates is {} when the merge already happened (idempotent).
    """
    keep, drop = canonicalize(keep), canonicalize(drop)
    registry = Registry({k: v for k, v in atoms.items() if k.startswith(TERM_PREFIX)})
    if keep == drop:
        raise ValueError("keep and drop are the same term")
    if keep not in registry.rows:
        raise ValueError("unknown term '%s' (keep must be a registered term)" % keep)
    if drop not in registry.rows:
        if registry.alias_of.get(drop) == keep:
            return {}, {}, "SUCCESS: '%s' is already an alias of '%s'; nothing to do" % (drop, keep)
        raise ValueError("unknown term '%s' (drop must be a registered term)" % drop)
    keep_row, drop_row = registry.rows[keep], registry.rows[drop]
    status = KNOWN if KNOWN in (keep_row["status"], drop_row["status"]) else keep_row["status"]
    aliases = set(keep_row["aliases"]) | set(drop_row["aliases"]) | {drop}
    definition = keep_row["definition"] or drop_row["definition"]
    term_ops = {TERM_PREFIX + keep: term_atom(keep, status, definition, aliases), TERM_PREFIX + drop: None}
    updates = {}
    for key, atom in atoms.items():
        if not key.startswith(SEMANTIC_PREFIX):
            continue
        metadata = _parse_memory(atom)
        if not metadata or not _evidence_of(metadata):
            continue
        statement = metadata["formalization"]
        if drop not in statement_terms(statement):
            continue
        renamed = serialize(rename_term(statement, drop, keep))
        metadata = dict(metadata, formalization=renamed, formalization_hash=statement_hash(renamed))
        updates[key[len(SEMANTIC_PREFIX):]] = metadata
    return updates, term_ops, "SUCCESS: merged '%s' into '%s' (%d statement(s) rewritten)" % (
        drop, keep, len(updates))


# -- backfill (F) --------------------------------------------------------------

def load_seed_terms(iter_dir):
    path = os.path.join(str(iter_dir), "seeds", "kb_terms.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            entries = json.load(handle)
    except (OSError, ValueError):
        return []
    return [entry for entry in entries if isinstance(entry, dict) and entry.get("name")]


def plan_backfill(atoms, seed_terms=()):
    """(updates, term_ops, summary) bringing pre-M5 formalizations and the seed vocabulary in."""
    registry = Registry({k: v for k, v in atoms.items() if k.startswith(TERM_PREFIX)})
    term_ops = {}
    for entry in seed_terms:
        name = canonicalize(entry["name"])
        row = registry.rows.get(name)
        if row and row["status"] == KNOWN:
            continue
        aliases = set(row["aliases"]) if row else set()
        aliases |= set(_aliases_list(entry.get("aliases")))
        aliases.discard(name)
        definition = (row or {}).get("definition") or entry.get("definition", "")
        term_ops[TERM_PREFIX + name] = term_atom(name, KNOWN, definition, aliases)
    # Seed rows become visible to alias resolution of the memories below.
    merged = dict({k: v for k, v in atoms.items() if k.startswith(TERM_PREFIX)}, **term_ops)
    registry = Registry(merged)

    updates = {}
    skipped = 0
    for key, atom in sorted(atoms.items()):
        if not key.startswith(SEMANTIC_PREFIX):
            continue
        metadata = _parse_memory(atom)
        if not metadata:
            continue
        text = metadata.get("formalization")
        if not text or metadata.get("formalization_hash") or metadata.get("formalization_error"):
            continue
        try:
            statement, _ = canonical_statement(str(text), resolve=registry.resolve)
        except ValueError as error:
            metadata = dict(metadata, formalization_error=str(error))
            skipped += 1
        else:
            metadata = dict(metadata, formalization=statement, formalization_hash=statement_hash(statement))
        updates[key[len(SEMANTIC_PREFIX):]] = metadata
    return updates, term_ops, skipped


def backfill_operations(atoms, seed_terms=()):
    """(memory ops + kb ops, expected, summary line or None) for one backfill pass."""
    from iterbrow_runtime.cognitive_events import metta_string as _quote
    updates, term_ops, skipped = plan_backfill(atoms, seed_terms)
    if not updates and not term_ops:
        return [], {}, None
    kb_ops, expected = plan_memory_change(atoms, updates, term_ops)
    memory_ops = []
    for memory_id, metadata in sorted(updates.items()):
        key = SEMANTIC_PREFIX + memory_id
        document = _document_of(atoms[key])
        memory_ops.append({"op": "upsert", "key": key, "atom": "(semantic-memory %s %s %s)" % (
            _quote(memory_id), _quote(document),
            _quote(json.dumps(metadata, sort_keys=True, ensure_ascii=False)))})
        expected[key] = atoms[key]
    statements = len({op["key"] for op in kb_ops if op["op"] == "upsert" and op["key"].startswith(STATEMENT_PREFIX)})
    new_terms = [op for op in kb_ops if op["op"] == "upsert" and op["key"].startswith(TERM_PREFIX)]
    provisional = sum(1 for op in new_terms if parse_term_atom(op["atom"])["status"] == PROVISIONAL)
    summary = "kb backfill: %d statements, %d terms (%d provisional), %d skipped" % (
        statements, len(new_terms), provisional, skipped)
    return memory_ops + kb_ops, expected, summary


def _document_of(atom):
    from iterbrow_runtime.cognitive_events import parse_semantic_atom
    return parse_semantic_atom(None, atom)[1]
