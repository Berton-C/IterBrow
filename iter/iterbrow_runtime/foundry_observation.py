"""Bounded mechanical observers; no semantic approval, execution or state writes.

Syntax coverage is explicit. Data expectations describe an exact authorized
delta, not an exemption from preserving other records. The caller binds these
inputs into the selected action and its authorization/snapshot identity.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


MAX_FILES = 512
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_RECORD_BYTES = 256 * 1024
MAX_DATA_BYTES = 8 * 1024 * 1024
MAX_EXPECTATIONS = 100
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _reject_nonfinite(value):
    raise ValueError("nonfinite JSON: " + value)


def _path(root, relative):
    if (not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative
            or relative.startswith("/") or any(part in ("", ".", "..") for part in relative.split("/"))):
        raise ValueError("syntax scope paths must be canonical project-relative paths")
    path = root / relative
    for index in range(1, len(Path(relative).parts) + 1):
        if (root / Path(*Path(relative).parts[:index])).is_symlink():
            raise ValueError("syntax scope cannot contain symlinks")
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("syntax scope must name an existing source file")
    return path


def observe_static(source_root, *, files=None, node_executable=None, timeout=10):
    """Observe syntax for an exact scope, never import/run candidate modules.

    Unsupported formats remain writable/buildable; their syntax is unvalidated
    by this observer. A selected subset never claims coverage of omitted files.
    """
    root = Path(source_root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("syntax observation requires an unaliased source directory")
    scope = "all-source-files" if files is None else "selected-files"
    if files is None:
        selected = []
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError("syntax source tree contains a symlink")
            if path.is_file():
                selected.append(path.relative_to(root).as_posix())
                if len(selected) > MAX_FILES:
                    raise ValueError("syntax observation exceeds bounded file scope")
    else:
        if not isinstance(files, list) or len(files) > MAX_FILES:
            raise ValueError("syntax files must be a bounded list")
        if any(not isinstance(name, str) for name in files) or len(set(files)) != len(files):
            raise ValueError("syntax files must be unique relative paths")
        selected = sorted(files)
    paths = [(name, _path(root, name)) for name in selected]
    node = node_executable or shutil.which("node")
    timeout = max(0.1, min(float(timeout), 30.0))
    deadline = time.monotonic() + timeout
    results = []
    for relative, path in paths:
        suffix = path.suffix.lower()
        language = {".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
                    ".py": "python", ".pyw": "python", ".json": "json"}.get(suffix, "unvalidated")
        result = {"path": relative, "language": language, "status": "unvalidated", "diagnostic": "no syntax adapter for this format"}
        if time.monotonic() >= deadline:
            result["diagnostic"] = "bounded syntax observation deadline exhausted"
            results.append(result)
            continue
        if language == "unvalidated":
            results.append(result)
            continue
        if path.stat().st_size > MAX_SOURCE_BYTES:
            result["diagnostic"] = "source exceeds the bounded syntax observer size"
            results.append(result)
            continue
        raw = path.read_bytes()
        result["source_hash"] = hashlib.sha256(raw).hexdigest()
        try:
            text = raw.decode("utf-8")
            if language == "python":
                # Parsing plus compile catches top-level await/return without
                # importing, running bytecode, writing pycache or resolving deps.
                compile(ast.parse(text, filename=relative), relative, "exec")
            elif language == "json":
                json.loads(text, parse_constant=_reject_nonfinite)
            else:
                if not node:
                    result["diagnostic"] = "JavaScript syntax observer is unavailable"
                    results.append(result)
                    continue
                completed = subprocess.run([str(node), "--check", str(path)],
                    cwd=str(root), capture_output=True, text=True, timeout=max(0.01, deadline - time.monotonic()),
                    # Do not inherit NODE_OPTIONS/loader hooks or credentials.
                    env={"PATH": os.defpath, "LANG": "C.UTF-8"})
                result["exit_code"] = completed.returncode
                if completed.returncode:
                    result.update(status="failed", diagnostic=completed.stderr[-4000:])
                    results.append(result)
                    continue
            result.update(status="passed", diagnostic="syntax checked without execution")
        except (SyntaxError, UnicodeError, ValueError) as exc:
            result.update(status="failed", diagnostic=(type(exc).__name__ + ": " + str(exc))[-4000:])
        except (OSError, subprocess.TimeoutExpired) as exc:
            result.update(status="unvalidated", diagnostic=(type(exc).__name__ + ": " + str(exc))[-4000:])
        if not path.exists() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != result["source_hash"]:
            result.update(status="unvalidated", diagnostic="source changed during syntax observation")
        results.append(result)
    statuses = [row["status"] for row in results]
    proof = "failed" if "failed" in statuses else "unknown" if not statuses or "unvalidated" in statuses else "passed"
    return {"proofs": {"syntax": proof}, "scope": scope, "selected_files": selected,
            "coverage": {"checked": sum(status in ("passed", "failed") for status in statuses),
                         "unvalidated": statuses.count("unvalidated"), "total": len(results)},
            "files": results, "exit_code": 1 if proof == "failed" else 0}


def _identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("invalid application collection/record identity")
    return value


def _record(value, expected_id=None):
    if not isinstance(value, dict):
        raise ValueError("application records must be objects")
    record_id = _identifier(value.get("id"))
    if expected_id is not None and record_id != expected_id:
        raise ValueError("expected record identity differs from its scoped record_id")
    encoded = _canonical(value)
    if len(encoded.encode("utf-8")) > MAX_RECORD_BYTES:
        raise ValueError("record exceeds bounded comparison size")
    return json.loads(encoded)


def _records(value):
    if not isinstance(value, dict):
        raise ValueError("application data must map collections to record lists")
    encoded = _canonical(value)
    if len(encoded.encode("utf-8")) > MAX_DATA_BYTES:
        raise ValueError("application data exceeds bounded comparison size")
    result = {}
    for collection, rows in value.items():
        _identifier(collection)
        if not isinstance(rows, list):
            raise ValueError("application collections must contain record lists")
        for row in rows:
            record = _record(row)
            key = (collection, record["id"])
            if key in result:
                raise ValueError("duplicate application record identity")
            result[key] = record
    return result


def compare_app_data(before_records, after_records, data_expectations=None):
    """Require exact named changes and preserve every other observed record.

    Expectations are [{collection, record_id, before: object|null,
    after: object|null}]. None means absent, never a wildcard. This observer
    does not grant authority, undo changes, or claim data-recovery capability.
    """
    before, after = _records(before_records), _records(after_records)
    expectations = [] if data_expectations is None else data_expectations
    if not isinstance(expectations, list) or len(expectations) > MAX_EXPECTATIONS:
        raise ValueError("data expectations must be a bounded list")
    if len(_canonical(expectations).encode("utf-8")) > MAX_DATA_BYTES:
        raise ValueError("data expectations exceed bounded comparison size")
    expected = {}
    for row in expectations:
        if not isinstance(row, dict) or set(row) != {"collection", "record_id", "before", "after"}:
            raise ValueError("data expectation must contain exactly collection, record_id, before, after")
        key = (_identifier(row["collection"]), _identifier(row["record_id"]))
        if key in expected:
            raise ValueError("duplicate data expectation identity")
        expected[key] = {"collection": key[0], "record_id": key[1],
                         "before": None if row["before"] is None else _record(row["before"], key[1]),
                         "after": None if row["after"] is None else _record(row["after"], key[1])}
    differences = {}
    for key in sorted(set(before) | set(after)):
        if _canonical(before.get(key)) != _canonical(after.get(key)):
            differences[key] = {"collection": key[0], "record_id": key[1], "before": before.get(key), "after": after.get(key)}
    mismatches = []
    for key in sorted(set(differences) | set(expected)):
        actual, wanted = differences.get(key), expected.get(key)
        if wanted is None:
            reason = "unexpected-change"
        elif actual is None:
            reason = "unused-expectation"
        elif _canonical(actual) != _canonical(wanted):
            reason = "expected-delta-mismatch"
        else:
            continue
        mismatches.append({"collection": key[0], "record_id": key[1], "reason": reason,
                           "actual": actual, "expected": wanted})
    matches = not mismatches
    return {"proofs": {"data-preserved": "passed" if matches else "failed"},
            "expected_match": matches, "differences": list(differences.values()),
            "expected_effects": list(expected.values()), "mismatches": mismatches,
            "unrelated_records_preserved": not any(item["reason"] == "unexpected-change" for item in mismatches)}
