"""One-time admission of accumulated legacy cognition into AtomSpace v1.

The source files remain untouched as compatibility projections and indexes.
This module only reads their current values, converts them to the same keyed
atoms used by authority-first writers, and commits one idempotent migration
transaction. Embeddings are deliberately excluded: they remain a rebuildable
semantic index, while memory identity, document, and metadata become native
atoms.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


MIGRATION_ID = "legacy-cognition-v1"
MIGRATION_KEY = "state:migration:%s" % MIGRATION_ID
MIGRATION_TRANSACTION_ID = "migration:%s" % MIGRATION_ID

_NACE_RE = re.compile(r"^\(([^\s()]+)(?:\s+([^\s()]+))?\s+\(stv\s+")
_TASK_RE = re.compile(
    r'^\(task-phase\s+("(?:\\.|[^"\\])*")\s+([a-z]+)\s+'
    r'("(?:\\.|[^"\\])*")\)$'
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _metta_string(value):
    return json.dumps(str(value), ensure_ascii=False)


def _source_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _logical_units(text):
    depth = 0
    buffer = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        in_string = False
        cut = len(line)
        for index, char in enumerate(line):
            if char == '"' and (index == 0 or line[index - 1] != "\\"):
                in_string = not in_string
            elif char == ";" and not in_string:
                cut = index
                break
        line = line[:cut].rstrip()
        if not line:
            continue
        buffer.append(line)
        depth += line.count("(") - line.count(")")
        if depth <= 0:
            yield " ".join(buffer)
            buffer = []
            depth = 0
    if buffer:
        raise RuntimeError("unbalanced legacy MeTTa unit")


def _strip_comment(line):
    in_string = False
    for index, char in enumerate(line):
        if char == '"' and (index == 0 or line[index - 1] != "\\"):
            in_string = not in_string
        elif char == ";" and not in_string:
            return line[:index].strip()
    return line.strip()


def _json_object(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("legacy state must be a JSON object: %s" % path)
    return value


def _add_nace(iter_dir, operations, summary, source_hashes):
    path = iter_dir / "nace_beliefs.metta"
    if not path.is_file():
        return
    count = 0
    for unit in _logical_units(path.read_text(encoding="utf-8", errors="strict")):
        match = _NACE_RE.match(unit)
        if match:
            identity = match.group(1)
            if match.group(2):
                identity += ":" + match.group(2)
        else:
            identity = "legacy:" + hashlib.sha256(unit.encode("utf-8")).hexdigest()
        operations.append({
            "op": "upsert",
            "key": "state:nace_belief:%s" % identity,
            "atom": unit,
        })
        count += 1
    summary["nace_beliefs"] = count
    source_hashes["nace_beliefs.metta"] = _source_hash(path)


def _add_tasks(iter_dir, operations, summary, source_hashes):
    path = iter_dir / "task_state.metta"
    if not path.is_file():
        return
    latest = {}
    for raw in path.read_text(encoding="utf-8", errors="strict").splitlines():
        # task_state's writer emits exactly one atom per line. Historical
        # notes legitimately contain unmatched parentheses inside quoted
        # prose, so a structural counter must not interpret that prose.
        unit = _strip_comment(raw)
        if not unit:
            continue
        match = _TASK_RE.match(unit)
        if not match:
            continue
        label = json.loads(match.group(1))
        latest[label] = unit
    for label, unit in sorted(latest.items()):
        operations.append({
            "op": "upsert",
            "key": "state:task:%s" % label,
            "atom": unit,
        })
    summary["tasks"] = len(latest)
    source_hashes["task_state.metta"] = _source_hash(path)


def _add_semantic_memory(iter_dir, operations, summary, source_hashes):
    path = iter_dir / "chroma_db" / "memories.json"
    if not path.is_file():
        return
    database = _json_object(path)
    ids = database.get("ids")
    documents = database.get("documents")
    metadatas = database.get("metadatas")
    embeddings = database.get("embeddings")
    if not all(isinstance(value, list) for value in (ids, documents, metadatas, embeddings)):
        raise RuntimeError("semantic-memory projection has invalid parallel arrays")
    if len({len(ids), len(documents), len(metadatas), len(embeddings)}) != 1:
        raise RuntimeError("semantic-memory projection arrays have different lengths")
    if len(set(str(item_id) for item_id in ids)) != len(ids):
        raise RuntimeError("semantic-memory projection contains duplicate ids")
    for item_id, document, metadata in zip(ids, documents, metadatas):
        item_id = str(item_id)
        atom = "(semantic-memory %s %s %s)" % (
            _metta_string(item_id),
            _metta_string(document),
            _metta_string(json.dumps(metadata or {}, sort_keys=True, ensure_ascii=False)),
        )
        operations.append({
            "op": "upsert",
            "key": "state:semantic_memory:%s" % item_id,
            "atom": atom,
        })
    summary["semantic_memories"] = len(ids)
    source_hashes["chroma_db/memories.json"] = _source_hash(path)


def _add_json_state(iter_dir, operations, summary, source_hashes):
    sources = (
        ("memory/soul_state.json", "state:soul:evaluation", "soul-state", "soul_state"),
        (
            "memory/soul_skills.json",
            "state:soul_skill:registry",
            "soul-skill-registry",
            "soul_skill_registry",
        ),
    )
    for relative, key, atom_name, summary_key in sources:
        path = iter_dir / relative
        if not path.is_file():
            continue
        value = _json_object(path)
        operations.append({
            "op": "upsert",
            "key": key,
            "atom": "(%s %s)" % (atom_name, _metta_string(_canonical(value))),
        })
        summary[summary_key] = 1
        source_hashes[relative] = _source_hash(path)


def _add_reliability(iter_dir, operations, summary, source_hashes):
    relative = "transformations/.runtime/tool_reliability.json"
    path = iter_dir / relative
    if not path.is_file():
        return
    scores = _json_object(path)
    for tool_name, score in sorted(scores.items()):
        if not isinstance(score, dict):
            raise RuntimeError("tool reliability entry is not an object: %s" % tool_name)
        operations.append({
            "op": "upsert",
            "key": "state:tool_reliability:%s" % tool_name,
            "atom": "(tool-reliability %s (stv %s %s) %s %s %s)" % (
                _metta_string(tool_name),
                score.get("f", 0.5),
                score.get("c", 0.0),
                score.get("calls", 0),
                score.get("successes", 0),
                score.get("failures", 0),
            ),
        })
    summary["tool_reliability"] = len(scores)
    source_hashes[relative] = _source_hash(path)


def collect_legacy_state(iter_dir):
    iter_dir = Path(iter_dir).resolve()
    operations = []
    summary = {}
    source_hashes = {}
    _add_nace(iter_dir, operations, summary, source_hashes)
    _add_tasks(iter_dir, operations, summary, source_hashes)
    _add_semantic_memory(iter_dir, operations, summary, source_hashes)
    _add_json_state(iter_dir, operations, summary, source_hashes)
    _add_reliability(iter_dir, operations, summary, source_hashes)
    return operations, summary, source_hashes


def migrate_legacy_state(store, rebuild_engine, iter_dir):
    if MIGRATION_KEY in store.atoms:
        return {
            "status": "already_migrated",
            "commit": store.commit,
            "summary": {},
        }
    operations, summary, source_hashes = collect_legacy_state(iter_dir)
    if not operations:
        return {"status": "not_needed", "commit": store.commit, "summary": {}}
    marker = {
        "migration_id": MIGRATION_ID,
        "summary": summary,
        "source_hashes": source_hashes,
    }
    operations.append({
        "op": "add",
        "key": MIGRATION_KEY,
        "atom": "(migration-complete %s %s)" % (
            _metta_string(MIGRATION_ID), _metta_string(_canonical(marker))
        ),
    })
    result = store.transact(
        operations,
        actor="platform.migration",
        source="iterbrow_runtime.legacy_migration",
        transaction_id=MIGRATION_TRANSACTION_ID,
        rebuild_engine=rebuild_engine,
        metadata=marker,
    )
    return {
        "status": "migrated",
        "commit": result["commit"],
        "state_hash": result["state_hash"],
        "summary": summary,
        "source_hashes": source_hashes,
    }
