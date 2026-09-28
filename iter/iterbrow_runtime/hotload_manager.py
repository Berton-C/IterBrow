"""Immutable runtime generations for recoverable Iter self-extension.

Candidate code is copied into a complete, inert generation.  Validation only
parses/compiles and inspects structure; it never imports candidate modules.
Activation is a single atomic pointer update. Ordinary self-repair does not
require a PWQ card; explicitly selected cards retain current consent checks.
Probation is observed by the Electron-side supervisor through
``supervisor_check``; a candidate never promotes itself.
"""

from __future__ import annotations

import ast
import fcntl
import hashlib
import json
import os
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .pwq_protocol import PWQStore
from .pwq_protocol import HOTLOAD_GUARDIAN_PROOF


SCHEMA_VERSION = 1
MANAGED_ROOTS = ("tools", "transformations", "channels")
FIXED_TESTS = ("python_compile", "component_contract")
DEFAULT_REQUIRED_HEARTBEATS = 3
DEFAULT_HEARTBEAT_TIMEOUT = 720.0


class HotloadError(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _fsync_directory(path):
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))
    _fsync_directory(path.parent)


def _atomic_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))
    _fsync_directory(path.parent)


def _read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _safe_relative(path):
    candidate = Path(str(path))
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise HotloadError("managed path must be relative and cannot traverse parents")
    if candidate.parts[0] not in MANAGED_ROOTS:
        raise HotloadError("path is outside the managed hot-load surface: %s" % path)
    if len(candidate.parts) != 2:
        raise HotloadError("v1 hot-load targets must be top-level runtime components: %s" % path)
    if candidate.suffix != ".py":
        raise HotloadError("only Python components can be hot-loaded in v1: %s" % path)
    if candidate.name.startswith(("_test", "_fixture")):
        raise HotloadError("test and fixture files are not runtime hot-load components: %s" % path)
    return candidate


class HotloadManager:
    def __init__(self, iter_root, runtime_dir=None, pwq_store=None):
        self.iter_root = Path(iter_root).resolve()
        self.runtime_dir = Path(runtime_dir or self.iter_root / ".runtime" / "hotload")
        self.generations_dir = self.runtime_dir / "generations"
        self.candidates_dir = self.runtime_dir / "candidates"
        self.active_path = self.runtime_dir / "active.json"
        self.events_path = self.runtime_dir / "events.jsonl"
        self.lock_path = self.runtime_dir / "writer.lock"
        self.heartbeat_path = self.iter_root / ".runtime" / "recovery" / "iter_heartbeat.json"
        self.heartbeat_completions_dir = (
            self.iter_root / ".runtime" / "recovery" / "cycle_completions"
        )
        self.pwq_store = pwq_store or PWQStore(
            self.iter_root / ".runtime" / "pwq",
            self.iter_root / ".runtime" / "pwq.json",
        )
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.generations_dir.mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _locked(self):
        handle = self.lock_path.open("a+")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def _append_event(self, kind, payload):
        events = self._events(repair_tail=True)
        if self._last_ledger_tail_incomplete:
            recovery = self._build_event(
                events,
                "ledger_tail_recovered",
                {
                    "discarded_tail_sha256": self._last_ledger_tail_hash,
                    "recovered_event_count": len(events),
                },
            )
            self._append_event_line(recovery)
            events.append(recovery)
        event = self._build_event(events, kind, payload)
        self._append_event_line(event)
        return event

    @staticmethod
    def _build_event(events, kind, payload):
        previous_hash = events[-1]["event_hash"] if events else "GENESIS"
        sequence = len(events) + 1
        event = {
            "schema_version": SCHEMA_VERSION,
            "sequence": sequence,
            "event_id": str(uuid.uuid4()),
            "kind": kind,
            "at": time.time(),
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event["event_hash"] = _sha256_bytes(_canonical(event).encode("utf-8"))
        return event

    def _append_event_line(self, event):
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(event) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(self.events_path.parent)

    def _events(self, repair_tail=False):
        self._last_ledger_tail_incomplete = False
        self._last_ledger_tail_hash = None
        if not self.events_path.exists():
            return []
        events = []
        previous_hash = "GENESIS"
        raw = self.events_path.read_bytes()
        ended_with_newline = raw.endswith(b"\n")
        lines = raw.split(b"\n")
        if ended_with_newline:
            lines = lines[:-1]
        for index, raw_line in enumerate(lines):
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                if index == len(lines) - 1 and not ended_with_newline:
                    self._last_ledger_tail_incomplete = True
                    self._last_ledger_tail_hash = _sha256_bytes(raw_line)
                    break
                raise HotloadError("hot-load event ledger corruption at line %d" % (index + 1)) from exc
            supplied_hash = event.pop("event_hash", None)
            actual_hash = _sha256_bytes(_canonical(event).encode("utf-8"))
            if (
                supplied_hash != actual_hash
                or event.get("previous_hash") != previous_hash
                or int(event.get("sequence", -1)) != len(events) + 1
            ):
                raise HotloadError("hot-load event hash chain mismatch at line %d" % (index + 1))
            event["event_hash"] = supplied_hash
            events.append(event)
            previous_hash = supplied_hash
        if repair_tail and (self._last_ledger_tail_incomplete or not ended_with_newline):
            canonical_ledger = "".join(_canonical(event) + "\n" for event in events)
            _atomic_text(self.events_path, canonical_ledger)
        return events

    def _completion_events(self):
        """Read immutable completed-cycle evidence written by Iter.

        The latest heartbeat remains useful for liveness and failure phases,
        but it is intentionally overwriteable.  Promotion evidence is not:
        every completed cycle is stored under a content-derived filename and
        verified before the external supervisor may count it.
        """
        if not self.heartbeat_completions_dir.exists():
            return []
        events = []
        for path in sorted(self.heartbeat_completions_dir.glob("*.json")):
            try:
                event = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise HotloadError(
                    "completed-cycle evidence is unreadable: %s" % path.name
                ) from exc
            supplied_hash = event.pop("event_hash", None)
            actual_hash = _sha256_bytes(_canonical(event).encode("utf-8"))
            heartbeat_id = str(event.get("heartbeat_id", ""))
            expected_name = _sha256_bytes(heartbeat_id.encode("utf-8")) + ".json"
            if (
                supplied_hash != actual_hash
                or not heartbeat_id
                or path.name != expected_name
                or event.get("phase") != "cycle_complete"
            ):
                raise HotloadError(
                    "completed-cycle evidence failed integrity verification: %s"
                    % path.name
                )
            event["event_hash"] = supplied_hash
            events.append(event)
        return sorted(
            events,
            key=lambda event: (
                float(event.get("at", 0)),
                int(event.get("sequence", 0)),
                str(event.get("heartbeat_id", "")),
            ),
        )

    def _copy_tree(self, source, target):
        source = Path(source)
        if not source.exists():
            target.mkdir(parents=True, exist_ok=True)
            return
        for item in source.rglob("*"):
            relative = item.relative_to(source)
            if "__pycache__" in relative.parts or ".runtime" in relative.parts:
                continue
            if item.is_symlink():
                raise HotloadError("symlink is forbidden in a managed generation: %s" % item)
            destination = target / relative
            if item.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            elif item.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(item), str(destination))

    def _tree_hash(self, generation_dir):
        digest = hashlib.sha256()
        root = Path(generation_dir)
        for path in sorted(root.rglob("*.py")):
            if path.is_symlink():
                raise HotloadError("symlink is forbidden in generation")
            relative = path.relative_to(root).as_posix()
            digest.update(relative.encode("utf-8") + b"\0")
            digest.update(path.read_bytes() + b"\0")
        return digest.hexdigest()

    def _generation_path(self, generation_id):
        if not generation_id or "/" in generation_id or ".." in generation_id:
            raise HotloadError("invalid generation id")
        path = self.generations_dir / generation_id
        if not path.is_dir():
            raise HotloadError("unknown generation: %s" % generation_id)
        return path

    def _verify_generation(self, generation_id, expected_hash=None):
        path = self._generation_path(generation_id)
        manifest = _read_json(path / "generation.json")
        if not manifest or manifest.get("generation_id") != generation_id:
            raise HotloadError("generation manifest is missing or mismatched: %s" % generation_id)
        unexpected_files = []
        for item in path.rglob("*"):
            relative = item.relative_to(path)
            if relative.parts[0] in MANAGED_ROOTS:
                continue
            if relative.as_posix() == "generation.json":
                continue
            if item.is_file() or item.is_symlink():
                unexpected_files.append(relative.as_posix())
        if unexpected_files:
            raise HotloadError(
                "generation contains non-managed file(s): %s"
                % ", ".join(sorted(unexpected_files))
            )
        actual_hash = self._tree_hash(path)
        recorded_hash = expected_hash or manifest.get("tree_hash")
        if not recorded_hash or actual_hash != recorded_hash:
            raise HotloadError("generation content hash mismatch: %s" % generation_id)
        return path, manifest

    def _candidate_path(self, candidate_id):
        if not candidate_id or "/" in candidate_id or ".." in candidate_id:
            raise HotloadError("invalid candidate id")
        return self.candidates_dir / (candidate_id + ".json")

    def _read_candidate(self, candidate_id):
        candidate = _read_json(self._candidate_path(candidate_id))
        if not candidate:
            raise HotloadError("unknown candidate: %s" % candidate_id)
        return candidate

    def _write_candidate(self, candidate):
        _atomic_json(self._candidate_path(candidate["candidate_id"]), candidate)

    def _bootstrap_locked(self):
        active = _read_json(self.active_path)
        if active:
            self._generation_path(active["generation_id"])
            return active
        temporary = self.generations_dir / (".bootstrap-" + uuid.uuid4().hex)
        temporary.mkdir(parents=True)
        for root_name in MANAGED_ROOTS:
            self._copy_tree(self.iter_root / root_name, temporary / root_name)
        tree_hash = self._tree_hash(temporary)
        generation_id = "base-" + tree_hash[:16]
        destination = self.generations_dir / generation_id
        if destination.exists():
            shutil.rmtree(temporary)
        else:
            os.replace(str(temporary), str(destination))
            _fsync_directory(self.generations_dir)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "generation_id": generation_id,
            "parent_generation_id": None,
            "tree_hash": tree_hash,
            "created_at": time.time(),
            "origin": "source_tree_baseline",
            "changed_paths": [],
        }
        _atomic_json(destination / "generation.json", manifest)
        active = {
            "schema_version": SCHEMA_VERSION,
            "generation_id": generation_id,
            "previous_generation_id": None,
            "status": "stable",
            "candidate_id": None,
            "activated_at": time.time(),
        }
        _atomic_json(self.active_path, active)
        self._append_event("baseline_created", {"generation_id": generation_id, "tree_hash": tree_hash})
        return active

    def ensure_baseline(self):
        with self._locked():
            return self._bootstrap_locked()

    def active(self):
        with self._locked():
            return dict(self._bootstrap_locked())

    def component_snapshot(self):
        """Return one immutable generation and component roots for a whole cycle."""
        active = self.active()
        generation, manifest = self._verify_generation(active["generation_id"])
        # Reuse the existing journal. This is context, never a new activation
        # prerequisite; unavailable history must not disable healthy work.
        recovery = None
        try:
            for event in reversed(self._events()):
                if event["kind"] not in ("candidate_rolled_back", "stable_generation_rolled_back"):
                    continue
                payload = event["payload"]
                if payload.get("restored_generation_id") == active["generation_id"]:
                    recovery = {"event_id": event["event_id"], "at": event["at"],
                                "failed_generation_id": payload.get("failed_generation_id"),
                                "restored_generation_id": payload.get("restored_generation_id"),
                                "reason": str(payload.get("reason", ""))[:500]}
                break  # Never present an older rollback as the latest recovery.
        except Exception as error:
            # Historical observation is best-effort, including malformed ledger
            # shapes. Generation verification above and supervisor checks still
            # enforce the existing health/recovery rules.
            recovery = {"unavailable": str(error)[:300]}
        return {
            "generation_id": active["generation_id"],
            "status": active["status"],
            "roots": {name: generation / name for name in MANAGED_ROOTS},
            "changed_paths": list(manifest.get("changed_paths") or []),
            "latest_recovery": recovery,
        }

    def _normalise_contract(self, contract, changed_paths, parent_generation_id):
        if not isinstance(contract, dict):
            raise HotloadError("candidate contract must be an object")
        required = (
            "module_id", "version", "purpose", "source_pressure",
            "allowed_writes", "allowed_effects", "tests", "rollback_target",
            "provenance",
        )
        missing = [field for field in required if field not in contract]
        if missing:
            raise HotloadError("candidate contract is missing: %s" % ", ".join(missing))
        if contract["rollback_target"] != parent_generation_id:
            raise HotloadError("rollback_target must name the exact active parent generation")
        if sorted(contract["allowed_writes"]) != sorted(changed_paths):
            raise HotloadError("allowed_writes must exactly match changed paths")
        if contract["allowed_effects"] not in ([], ["managed-component-runtime"]):
            raise HotloadError("candidate requests effects outside the v1 membrane")
        tests = contract["tests"]
        if not isinstance(tests, list) or not tests:
            raise HotloadError("candidate must request fixed validation tests")
        unknown_tests = sorted(set(tests) - set(FIXED_TESTS))
        if unknown_tests:
            raise HotloadError("unknown or candidate-defined tests: %s" % unknown_tests)
        result = {field: contract[field] for field in required}
        if "atlas_slice" in contract:
            result["atlas_slice"] = contract["atlas_slice"]
        if "fitness_review" in contract:
            review = contract["fitness_review"]
            if not isinstance(review, dict) or not isinstance(review.get("revert_on_degradation"), bool):
                raise HotloadError("fitness_review requires a boolean revert_on_degradation")
            result["fitness_review"] = {"revert_on_degradation": review["revert_on_degradation"]}
        return result

    def stage(self, changes, contract):
        if not isinstance(changes, dict) or not changes:
            raise HotloadError("changes must be a non-empty path-to-content object")
        normalised = {}
        for supplied_path, content in changes.items():
            relative = _safe_relative(supplied_path)
            if content is not None and not isinstance(content, str):
                raise HotloadError("candidate content must be text or null for deletion")
            normalised[relative.as_posix()] = content
        with self._locked():
            active = self._bootstrap_locked()
            if active["status"] != "stable":
                raise HotloadError("cannot stage while another generation is in probation")
            parent_id = active["generation_id"]
            canonical_contract = self._normalise_contract(contract, list(normalised), parent_id)
            candidate_id = "candidate-" + uuid.uuid4().hex
            temporary = self.generations_dir / ("." + candidate_id + ".tmp")
            generation_path = self.generations_dir / candidate_id
            parent_generation, _parent_manifest = self._verify_generation(parent_id)
            temporary.mkdir(parents=True)
            for root_name in MANAGED_ROOTS:
                self._copy_tree(
                    parent_generation / root_name,
                    temporary / root_name,
                )
            for relative_text, content in normalised.items():
                target = temporary / relative_text
                if target.exists() and target.is_symlink():
                    raise HotloadError("candidate cannot replace a symlink")
                if content is None:
                    if target.exists():
                        target.unlink()
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")
            tree_hash = self._tree_hash(temporary)
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "generation_id": candidate_id,
                "parent_generation_id": parent_id,
                "tree_hash": tree_hash,
                "created_at": time.time(),
                "origin": "quarantined_candidate",
                "changed_paths": sorted(normalised),
                "change_hashes": {
                    path: None if content is None else _sha256_bytes(content.encode("utf-8"))
                    for path, content in sorted(normalised.items())
                },
                "contract": canonical_contract,
            }
            _atomic_json(temporary / "generation.json", manifest)
            os.replace(str(temporary), str(generation_path))
            _fsync_directory(self.generations_dir)
            candidate = {
                "schema_version": SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "generation_id": candidate_id,
                "parent_generation_id": parent_id,
                "status": "quarantined",
                "tree_hash": tree_hash,
                "contract": canonical_contract,
                "created_at": time.time(),
                "validation": None,
                "authorization": None,
                "observed_heartbeats": [],
            }
            self._write_candidate(candidate)
            self._append_event("candidate_staged", {
                "candidate_id": candidate_id,
                "parent_generation_id": parent_id,
                "tree_hash": tree_hash,
                "changed_paths": sorted(normalised),
            })
            return candidate

    @staticmethod
    def _component_contract(path, tree):
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        functions = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        if path.parts[0] == "tools" and not path.name.startswith("_"):
            return "DESCRIPTION" in names and "run" in functions, "public tool requires DESCRIPTION and run"
        if path.parts[0] == "transformations" and not path.name.startswith("_"):
            return "DESCRIPTION" in names and "transform" in functions, "public transformation requires DESCRIPTION and transform"
        if path.parts[0] == "channels" and not path.name.startswith("_"):
            return "receive" in functions, "public channel requires receive"
        return True, "private/helper component"

    def validate(self, candidate_id):
        with self._locked():
            candidate = self._read_candidate(candidate_id)
            if candidate["status"] not in ("quarantined", "validation_failed", "validated"):
                raise HotloadError("candidate cannot be validated from %s" % candidate["status"])
            generation, _manifest = self._verify_generation(
                candidate["generation_id"], candidate["tree_hash"]
            )
            results = []
            passed = True
            runtime_paths = []
            for root_name in MANAGED_ROOTS:
                runtime_paths.extend(
                    path for path in (generation / root_name).glob("*.py")
                    if not path.name.startswith(("_test", "_fixture"))
                )
            for path in sorted(runtime_paths):
                relative = path.relative_to(generation)
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative.as_posix())
                    compile(tree, relative.as_posix(), "exec")
                    contract_ok, detail = self._component_contract(relative, tree)
                    if not contract_ok:
                        passed = False
                    results.append({"path": relative.as_posix(), "passed": contract_ok, "detail": detail})
                except (SyntaxError, UnicodeError) as exc:
                    passed = False
                    results.append({"path": relative.as_posix(), "passed": False, "detail": "%s: %s" % (type(exc).__name__, exc)})
            candidate["status"] = "validated" if passed else "validation_failed"
            candidate["validation"] = {
                "at": time.time(),
                "passed": passed,
                "fixed_tests": list(FIXED_TESTS),
                "results": results,
                "candidate_executed": False,
            }
            self._write_candidate(candidate)
            self._append_event("candidate_validated" if passed else "candidate_validation_failed", {
                "candidate_id": candidate_id,
                "passed": passed,
                "failure_count": len([result for result in results if not result["passed"]]),
            })
            return candidate

    def supersede_candidate(self, candidate_id, replacement_candidate_id):
        """Retire an inert candidate while preserving its immutable evidence."""
        with self._locked():
            active = self._bootstrap_locked()
            if active.get("candidate_id") == candidate_id:
                raise HotloadError("an active/probation candidate cannot be superseded")
            candidate = self._read_candidate(candidate_id)
            replacement = self._read_candidate(replacement_candidate_id)
            if candidate.get("status") not in (
                    "quarantined", "validation_failed", "validated"):
                raise HotloadError("candidate cannot be superseded from %s" % candidate.get("status"))
            if replacement.get("status") != "validated" or not (
                    replacement.get("validation") or {}).get("passed"):
                raise HotloadError("replacement candidate must be validated")
            if replacement.get("parent_generation_id") != active.get("generation_id"):
                raise HotloadError("replacement candidate does not target the active parent")
            self._verify_generation(
                replacement["generation_id"], replacement["tree_hash"]
            )
            candidate["status"] = "superseded"
            candidate["superseded_at"] = time.time()
            candidate["replacement_candidate_id"] = replacement_candidate_id
            self._write_candidate(candidate)
            self._append_event("candidate_superseded", {
                "candidate_id": candidate_id,
                "replacement_candidate_id": replacement_candidate_id,
                "retained_generation_id": candidate["generation_id"],
            })
            proposal_id = "hotload:" + candidate_id
            replacement_proposal_id = "hotload:" + replacement_candidate_id
            board = self.pwq_store.read()
            item = next(
                (entry for entry in board.get("items", []) if entry.get("id") == proposal_id),
                None,
            )
            if item and item.get("status") not in ("completed", "rejected", "superseded"):
                self.pwq_store.command(
                    "supersede", proposal_id, actor="platform.hotload_guardian",
                    payload={"replacement_proposal_id": replacement_proposal_id},
                    expected_version=item.get("proposal_version"),
                    command_id="supersede:%s:%s" % (
                        candidate_id, replacement_candidate_id,
                    ),
                )
            return candidate

    def _verify_authorization(self, proposal_id, dispatch_authorization, candidate=None):
        board = self.pwq_store.read()
        item = next((entry for entry in board.get("items", []) if entry.get("id") == proposal_id), None)
        if not item:
            raise HotloadError("PWQ proposal does not exist")
        if item.get("work_class") != "build":
            raise HotloadError("hot-load activation requires a build-class PWQ proposal")
        approval_status = item.get("approval_status") or {}
        if not approval_status.get("ready"):
            raise HotloadError("PWQ approval threshold and required roles are not satisfied")
        scope = item.get("authorization_scope") or {}
        if scope.get("action") == "hotload.activate":
            if candidate is None or scope != self.candidate_authorization_scope(candidate):
                raise HotloadError("PWQ authorization is not bound to this exact candidate")
        elif scope.get("action") == "hotload.revise":
            if not self._scope_covers_revision(scope, candidate):
                raise HotloadError("revision is outside the approved work's managed paths")
        elif scope:
            raise HotloadError("PWQ work does not authorize managed runtime revisions")
        if item.get("status") not in ("approved", "in_progress"):
            raise HotloadError("PWQ proposal is not approved for dispatch")
        if not dispatch_authorization or item.get("dispatch_authorization") != dispatch_authorization:
            raise HotloadError("current PWQ dispatch authorization is required")
        if item.get("status") == "approved":
            board = self.pwq_store.command(
                "start", proposal_id, actor="iter",
                payload={"dispatch_authorization": dispatch_authorization},
                expected_version=item.get("proposal_version"),
                command_id="dispatch:" + proposal_id + ":v" + str(item.get("proposal_version")),
            )
            item = next(entry for entry in board["items"] if entry.get("id") == proposal_id)
        if item.get("status") != "in_progress":
            raise HotloadError("PWQ work did not enter in_progress dispatch state")
        return {
            "proposal_id": proposal_id,
            "proposal_version": item.get("proposal_version"),
            "dispatch_authorization": dispatch_authorization,
            "last_event_id": item.get("last_event_id"),
            "proposal_digest": item.get("proposal_digest"),
            "authorization_evidence_digest": item.get("authorization_evidence_digest"),
            "authorization_scope": scope,
        }

    @staticmethod
    def _scope_covers_revision(scope, candidate):
        """One approved work item can cover successive repairs to named files.

        Exact relative paths only: no wildcards, authority files or inferred
        expansion. Candidate validation and external recovery remain unchanged.
        """
        paths = scope.get("allowed_writes")
        if not candidate or not isinstance(paths, list) or not paths:
            return False
        try:
            allowed = {_safe_relative(path).as_posix() for path in paths}
        except (HotloadError, TypeError, ValueError):
            return False
        changed = candidate.get("contract", {}).get("allowed_writes", [])
        return bool(changed) and set(changed).issubset(allowed)

    def approved_revision_work(self, candidate, proposal_id=""):
        """Resolve current consent from the ledger, not model-copied tokens."""
        matches = [item for item in self.pwq_store.read().get("items", [])
                   if (not proposal_id or item.get("id") == proposal_id)
                   and item.get("work_class") == "build"
                   and item.get("status") in ("approved", "in_progress")
                   and (item.get("approval_status") or {}).get("ready")
                   and (item.get("authorization_scope") or {}).get("action") == "hotload.revise"
                   and self._scope_covers_revision(item["authorization_scope"], candidate)]
        if len(matches) != 1:
            raise HotloadError("specify one current approved repair work item covering these paths")
        return matches[0]

    @staticmethod
    def split_approval_policy():
        return {
            "scheme": "role_threshold_v1",
            "threshold": 2,
            "required_roles": ["human_owner", "runtime_guardian"],
            "distinct_signers": True,
            "eligible_signers": [
                {
                    "signer_id": "human:owner",
                    "role": "human_owner",
                    "actors": ["human"],
                    "proof_types": ["trusted_local_session_v1"],
                },
                {
                    "signer_id": "platform:hotload_guardian",
                    "role": "runtime_guardian",
                    "actors": ["platform.hotload_guardian"],
                    "proof_types": [HOTLOAD_GUARDIAN_PROOF],
                },
            ],
        }

    @staticmethod
    def candidate_authorization_scope(candidate):
        return {
            "action": "hotload.activate",
            "candidate_id": candidate["candidate_id"],
            "candidate_tree_hash": candidate["tree_hash"],
            "rollback_target": candidate["parent_generation_id"],
        }

    def attest_candidate(self, candidate_id, proposal_id):
        """Add the non-human validation/recovery witness to a split PWQ card."""
        with self._locked():
            active = self._bootstrap_locked()
            if active["status"] != "stable":
                raise HotloadError("technical attestation requires a stable active generation")
            candidate = self._read_candidate(candidate_id)
            validation = candidate.get("validation") or {}
            if candidate.get("status") != "validated" or not validation.get("passed"):
                raise HotloadError("candidate must pass fixed validation before guardian attestation")
            if validation.get("candidate_executed") is not False:
                raise HotloadError("candidate validation must remain non-executing")
            if candidate.get("parent_generation_id") != active.get("generation_id"):
                raise HotloadError("candidate rollback parent is no longer active")
            self._verify_generation(candidate["generation_id"], candidate["tree_hash"])
            board = self.pwq_store.read()
            item = next(
                (entry for entry in board.get("items", []) if entry.get("id") == proposal_id),
                None,
            )
            if not item:
                raise HotloadError("PWQ proposal does not exist")
            expected_scope = self.candidate_authorization_scope(candidate)
            if item.get("authorization_scope") != expected_scope:
                raise HotloadError("PWQ authorization scope does not bind this exact candidate")
            policy = item.get("approval_policy") or {}
            eligible = policy.get("eligible_signers") or []
            if not any(
                signer.get("signer_id") == "platform:hotload_guardian"
                and signer.get("role") == "runtime_guardian"
                for signer in eligible
            ):
                raise HotloadError("PWQ proposal does not request the runtime guardian role")
            evidence = {
                "candidate_id": candidate_id,
                "tree_hash": candidate["tree_hash"],
                "parent_generation_id": candidate["parent_generation_id"],
                "fixed_tests": validation.get("fixed_tests") or [],
                "candidate_executed": validation.get("candidate_executed"),
                "proposal_digest": item.get("proposal_digest"),
            }
            proof_value = hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()
            return self.pwq_store.command(
                "sign", proposal_id, actor="platform.hotload_guardian",
                payload={
                    "signer_id": "platform:hotload_guardian",
                    "role": "runtime_guardian",
                    "proof": {"type": HOTLOAD_GUARDIAN_PROOF, "value": proof_value},
                },
                expected_version=item.get("proposal_version"),
                command_id=(
                    "guardian:%s:v%s:%s" % (
                        candidate_id,
                        item.get("proposal_version"),
                        item.get("proposal_digest"),
                    )
                ),
            )

    def _track_candidate(self, candidate, atlas_slice, bounded_claim,
                         evidence_open_gaps, next_trigger, command_suffix):
        # Progress is a projection, not a health signal or a source of consent.
        # Real authorization is checked separately on activation and probation.
        if not (candidate.get("authorization") or {}).get("proposal_id"):
            return None
        try:
            return self._report_candidate(candidate, atlas_slice, bounded_claim,
                                          evidence_open_gaps, next_trigger, command_suffix)
        except Exception as exc:
            warning = {"candidate_id": candidate["candidate_id"],
                       "stage": command_suffix, "tracking_error": str(exc)}
            try:
                self._append_event("tracking_unavailable", warning)
            except Exception:
                pass  # Reporting failure must not undo a healthy revision.
            return warning

    def _report_candidate(self, candidate, atlas_slice, bounded_claim,
                          evidence_open_gaps, next_trigger, command_suffix):
        authorization = candidate.get("authorization") or {}
        proposal_id = authorization.get("proposal_id")
        if not proposal_id:
            raise HotloadError("candidate has no PWQ authorization to track")
        invariants = ["INV-14"] if atlas_slice == "HOT-2" else ["INV-15"]
        return self.pwq_store.command(
            "track", proposal_id, actor="platform.recovery",
            payload={
                "target": "Recoverable self-extension",
                "atlas_slice": atlas_slice,
                "bounded_claim": bounded_claim,
                "invariants": invariants,
                "evidence_open_gaps": evidence_open_gaps,
                "boundaries": (
                    "PWQ controls scope and dispatch; the candidate cannot approve or promote "
                    "itself; the exact parent generation remains the rollback target."
                ),
                "next_trigger": next_trigger,
                "source_revision": str(candidate.get("contract", {}).get("provenance", "")),
            },
            expected_version=authorization.get("proposal_version"),
            command_id="tracking:%s:%s" % (candidate["candidate_id"], command_suffix),
        )

    def _authorization_still_current(self, candidate):
        authorization = candidate.get("authorization") or {}
        if authorization.get("kind") == "ordinary_loop":
            return True  # Ordinary self-repair never acquired PWQ authority.
        board = self.pwq_store.read()
        item = next(
            (entry for entry in board.get("items", [])
             if entry.get("id") == authorization.get("proposal_id")),
            None,
        )
        return bool(
            item
            and item.get("status") in ("approved", "in_progress", "completed")
            and item.get("proposal_version") == authorization.get("proposal_version")
            and (item.get("approval_status") or {}).get("ready")
            and item.get("authorization_scope", {}) == authorization.get("authorization_scope", {})
            and item.get("authorization_evidence_digest") == authorization.get("authorization_evidence_digest")
        )

    def _require_live_parent(self, active, now=None):
        """Prove the stable parent is alive before consuming authorization.

        Activation changes the generation pointer at a cycle boundary.  A
        stopped process cannot cross that boundary, and startup recovery must
        continue to treat every probation pointer as abandoned.  Requiring a
        recent heartbeat from a live PID closes the gap between those rules.
        """
        observed_at = float(now if now is not None else time.time())
        heartbeat = _read_json(self.heartbeat_path)
        if not isinstance(heartbeat, dict):
            raise HotloadError("activation requires a live parent heartbeat")
        if heartbeat.get("generation_id") != active.get("generation_id"):
            raise HotloadError("activation heartbeat does not match the active parent generation")
        if heartbeat.get("hard_floor_ok") is False or heartbeat.get("phase") == "error":
            raise HotloadError("activation parent reported a hard health-floor failure")
        heartbeat_at = float(heartbeat.get("at", 0))
        if heartbeat_at <= 0 or observed_at - heartbeat_at > DEFAULT_HEARTBEAT_TIMEOUT:
            raise HotloadError("activation parent heartbeat is stale")
        try:
            heartbeat_pid = int(heartbeat.get("pid"))
            if heartbeat_pid <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise HotloadError("activation parent heartbeat has no valid process identity")
        try:
            os.kill(heartbeat_pid, 0)
        except ProcessLookupError:
            raise HotloadError("activation parent process is not running")
        except PermissionError:
            pass
        except OSError as exc:
            raise HotloadError("activation parent process cannot be verified: %s" % exc)
        return heartbeat

    def _pause_and_track_recovery(self, candidate, reason):
        authorization = candidate.get("authorization") or {}
        proposal_id = authorization.get("proposal_id")
        if not proposal_id:
            return None
        try:
            board = self.pwq_store.read()
            item = next(
                (entry for entry in board.get("items", []) if entry.get("id") == proposal_id),
                None,
            )
            reusable_work = (authorization.get("authorization_scope") or {}).get("action") == "hotload.revise"
            if item and item.get("status") == "in_progress" and not reusable_work:
                board = self.pwq_store.command(
                    "pause", proposal_id, actor="platform.recovery",
                    payload={"reason": reason},
                    expected_version=item.get("proposal_version"),
                    command_id="recovery-pause:" + candidate["candidate_id"],
                )
                item = next(entry for entry in board["items"] if entry.get("id") == proposal_id)
            if item and (item.get("status") == "paused" or
                         (reusable_work and item.get("status") == "in_progress")):
                return self._track_candidate(
                    candidate, "REC-1", "Restore the exact verified parent after a failed revision",
                    "Candidate rollback completed. Failure evidence: %s" % reason,
                    "Inspect failure evidence and repair within the existing work scope; ask only if scope changes.",
                    "rollback",
                )
        except Exception as exc:
            return {"tracking_error": "%s: %s" % (type(exc).__name__, exc)}
        return None

    def activate(self, candidate_id, proposal_id="", dispatch_authorization="",
                 required_heartbeats=DEFAULT_REQUIRED_HEARTBEATS,
                 heartbeat_timeout=DEFAULT_HEARTBEAT_TIMEOUT):
        with self._locked():
            active = self._bootstrap_locked()
            if active["status"] != "stable":
                raise HotloadError("another generation is already in probation")
            candidate = self._read_candidate(candidate_id)
            if candidate["status"] != "validated" or not candidate["validation"]["passed"]:
                raise HotloadError("candidate must pass fixed validation before activation")
            if candidate["parent_generation_id"] != active["generation_id"]:
                raise HotloadError("candidate parent is no longer the active generation")
            self._verify_generation(candidate["generation_id"], candidate["tree_hash"])
            parent_heartbeat = self._require_live_parent(active)
            authorization = self._verify_authorization(
                proposal_id, dispatch_authorization, candidate=candidate
            ) if proposal_id else {"kind": "ordinary_loop"}
            required = max(1, min(int(required_heartbeats), 20))
            timeout = max(30.0, min(float(heartbeat_timeout), 3600.0))
            candidate["status"] = "probation"
            candidate["authorization"] = authorization
            candidate["activated_at"] = time.time()
            candidate["required_heartbeats"] = required
            candidate["heartbeat_timeout"] = timeout
            candidate["observed_heartbeats"] = []
            if candidate["contract"].get("fitness_review"):
                from .revision_fitness import fitness_snapshot
                candidate["fitness_before"] = fitness_snapshot(self.iter_root)
            candidate["activation_parent_heartbeat"] = {
                "heartbeat_id": parent_heartbeat.get("heartbeat_id"),
                "generation_id": parent_heartbeat.get("generation_id"),
                "pid": parent_heartbeat.get("pid"),
                "session_id": parent_heartbeat.get("session_id"),
                "cycle": parent_heartbeat.get("cycle"),
                "sequence": parent_heartbeat.get("sequence"),
                "phase": parent_heartbeat.get("phase"),
                "at": parent_heartbeat.get("at"),
            }
            self._track_candidate(
                candidate, "HOT-2", "Activate one immutable generation at a cycle boundary",
                "Fixed admission checks passed without importing candidate code; live probation has not yet begun.",
                "Atomically activate the candidate and wait for externally observed completed cycles.",
                "admitted",
            )
            self._write_candidate(candidate)
            pointer = {
                "schema_version": SCHEMA_VERSION,
                "generation_id": candidate["generation_id"],
                "previous_generation_id": active["generation_id"],
                "status": "probation",
                "candidate_id": candidate_id,
                "activated_at": candidate["activated_at"],
                "required_heartbeats": required,
                "heartbeat_timeout": timeout,
            }
            _atomic_json(self.active_path, pointer)
            self._append_event("candidate_activated", {
                "candidate_id": candidate_id,
                "generation_id": candidate["generation_id"],
                "previous_generation_id": active["generation_id"],
                "pwq_proposal_id": proposal_id,
            })
            try:
                self._track_candidate(
                    candidate, "REC-1", "Externally supervise candidate probation",
                    "Candidate generation is active on probation; no completed candidate heartbeat has yet been admitted.",
                    "Promote only after the required distinct completed-cycle heartbeats; otherwise roll back before restart.",
                    "activated",
                )
            except Exception as exc:
                recovered = self._rollback_locked("PWQ Tracking failed after activation: %s" % exc)
                raise HotloadError(recovered["reason"])
            return pointer

    def _rollback_locked(self, reason):
        active = self._bootstrap_locked()
        if active["status"] != "probation":
            return {"action": "none", "reason": "no generation in probation", "active": active}
        candidate = self._read_candidate(active["candidate_id"])
        previous = active.get("previous_generation_id")
        self._generation_path(previous)
        candidate["status"] = "rolled_back"
        candidate["rolled_back_at"] = time.time()
        candidate["rollback_reason"] = reason
        self._write_candidate(candidate)
        pointer = {
            "schema_version": SCHEMA_VERSION,
            "generation_id": previous,
            "previous_generation_id": None,
            "status": "stable",
            "candidate_id": None,
            "activated_at": time.time(),
        }
        _atomic_json(self.active_path, pointer)
        self._append_event("candidate_rolled_back", {
            "candidate_id": candidate["candidate_id"],
            "failed_generation_id": candidate["generation_id"],
            "restored_generation_id": previous,
            "reason": reason,
        })
        tracking = self._pause_and_track_recovery(candidate, reason)
        result = {"action": "rolled_back", "reason": reason, "active": pointer, "candidate": candidate}
        if tracking and tracking.get("tracking_error"):
            result["tracking_error"] = tracking["tracking_error"]
        return result

    def _rollback_stable_locked(self, reason):
        active = self._bootstrap_locked()
        if active["status"] != "stable" or not active.get("previous_generation_id"):
            raise HotloadError("stable generation has no verified rollback target: %s" % reason)
        previous = active["previous_generation_id"]
        _path, previous_manifest = self._verify_generation(previous)
        candidate = None
        if active.get("candidate_id"):
            candidate = self._read_candidate(active["candidate_id"])
            candidate["status"] = "rolled_back_after_promotion"
            candidate["rolled_back_at"] = time.time()
            candidate["rollback_reason"] = reason
            self._write_candidate(candidate)
        pointer = {
            "schema_version": SCHEMA_VERSION,
            "generation_id": previous,
            "previous_generation_id": previous_manifest.get("parent_generation_id"),
            "status": "stable",
            "candidate_id": None,
            "activated_at": time.time(),
        }
        _atomic_json(self.active_path, pointer)
        self._append_event("stable_generation_rolled_back", {
            "failed_generation_id": active["generation_id"],
            "restored_generation_id": previous,
            "reason": reason,
        })
        tracking = self._pause_and_track_recovery(candidate, reason) if candidate else None
        result = {"action": "rolled_back", "reason": reason, "active": pointer, "candidate": candidate}
        if tracking and tracking.get("tracking_error"):
            result["tracking_error"] = tracking["tracking_error"]
        return result

    def rollback_probation(self, reason="manual emergency rollback"):
        with self._locked():
            return self._rollback_locked(reason)

    def recover_on_startup(self):
        with self._locked():
            active = self._bootstrap_locked()
            if active["status"] == "probation":
                return self._rollback_locked("abandoned probation recovered before Iter startup")
            try:
                self._verify_generation(active["generation_id"])
            except HotloadError as exc:
                if active.get("previous_generation_id"):
                    return self._rollback_stable_locked(str(exc))
                raise
            return {"action": "none", "active": active}

    def supervisor_check(self, iter_running, now=None, iter_pid=None,
                         iter_started_at=None):
        """Observe probation from outside Iter and promote or roll back."""
        observed_at = float(now if now is not None else time.time())
        with self._locked():
            active = self._bootstrap_locked()
            if active["status"] != "probation":
                try:
                    self._verify_generation(active["generation_id"])
                except HotloadError as exc:
                    if active.get("previous_generation_id"):
                        return self._rollback_stable_locked(str(exc))
                    return {
                        "action": "restart_required",
                        "reason": str(exc),
                        "active": active,
                    }
                if iter_running:
                    heartbeat = _read_json(self.heartbeat_path)
                    startup_age = (
                        observed_at - float(iter_started_at)
                        if iter_started_at is not None else 0.0
                    )
                    matching_process = (
                        heartbeat and (
                            iter_pid is None
                            or int(heartbeat.get("pid", -1)) == int(iter_pid)
                        )
                    )
                    if not matching_process:
                        if iter_started_at is not None and startup_age > 30.0:
                            return {
                                "action": "restart_required",
                                "reason": "Iter process did not establish its heartbeat",
                                "active": active,
                            }
                        return {"action": "waiting", "reason": "Iter startup heartbeat", "active": active}
                    if heartbeat.get("generation_id") != active["generation_id"]:
                        return {
                            "action": "restart_required",
                            "reason": "Iter is running a generation other than the active stable generation",
                            "active": active,
                        }
                    if observed_at - float(heartbeat.get("at", 0)) > DEFAULT_HEARTBEAT_TIMEOUT:
                        return {
                            "action": "restart_required",
                            "reason": "Iter cycle heartbeat is stale",
                            "active": active,
                        }
                return {"action": "none", "active": active}
            candidate = self._read_candidate(active["candidate_id"])
            try:
                self._verify_generation(candidate["generation_id"], candidate["tree_hash"])
            except HotloadError as exc:
                return self._rollback_locked(str(exc))
            if not self._authorization_still_current(candidate):
                return self._rollback_locked("PWQ authorization or approved build scope changed during probation")
            grace = min(10.0, float(active["heartbeat_timeout"]) / 3.0)
            if not iter_running:
                if observed_at - float(active["activated_at"]) >= grace:
                    return self._rollback_locked("Iter process exited during probation")
                return {"action": "waiting", "reason": "startup grace", "active": active}
            heartbeat = _read_json(self.heartbeat_path)
            if not heartbeat:
                if observed_at - float(active["activated_at"]) >= grace:
                    return self._rollback_locked("heartbeat missing during probation")
                return {"action": "waiting", "reason": "first heartbeat", "active": active}
            heartbeat_at = float(heartbeat.get("at", 0))
            if iter_pid is not None and int(heartbeat.get("pid", -1)) != int(iter_pid):
                if observed_at - float(active["activated_at"]) >= grace:
                    return self._rollback_locked("candidate process did not establish its heartbeat")
                return {"action": "waiting", "reason": "candidate process heartbeat", "active": active}
            if heartbeat_at < float(active["activated_at"]):
                # The parent generation is pinned for its entire in-flight
                # cycle.  A live parent heartbeat may therefore predate the
                # atomic activation pointer until the next cycle begins.
                # Process exit is handled above; only the full heartbeat
                # timeout makes this wait unsafe.
                if observed_at - heartbeat_at > float(active["heartbeat_timeout"]):
                    return self._rollback_locked("pre-activation parent heartbeat became stale")
                return {"action": "waiting", "reason": "new generation has not started", "active": active}
            if observed_at - heartbeat_at > float(active["heartbeat_timeout"]):
                return self._rollback_locked("heartbeat stale during probation")
            if heartbeat.get("generation_id") != active["generation_id"]:
                parent = candidate.get("activation_parent_heartbeat") or {}
                same_pinned_parent_cycle = bool(
                    heartbeat.get("generation_id") == active.get("previous_generation_id")
                    and heartbeat.get("pid") == parent.get("pid")
                    and heartbeat.get("session_id") == parent.get("session_id")
                    and heartbeat.get("cycle") == parent.get("cycle")
                )
                if same_pinned_parent_cycle:
                    return {
                        "action": "waiting",
                        "reason": "activation-time parent cycle is still finishing",
                        "active": active,
                    }
                return self._rollback_locked("Iter reported the wrong active generation")
            if heartbeat.get("hard_floor_ok") is False or heartbeat.get("phase") == "error":
                return self._rollback_locked("Iter reported a hard health-floor failure")

            # A single overwriteable heartbeat is a liveness signal, not a
            # lossless promotion ledger.  Prefer immutable completed-cycle
            # records and retain a narrow compatibility proof for an Iter
            # process that started before that ledger existed: reaching cycle
            # N in the same process/session proves that cycles before N passed
            # the hard-floor branch, because a failed cycle blocks there until
            # the external supervisor rolls it back.
            try:
                completion_events = self._completion_events()
            except HotloadError as exc:
                return self._rollback_locked(str(exc))
            completion_proofs = []
            current_session = heartbeat.get("session_id")
            current_pid = heartbeat.get("pid")
            for event in completion_events:
                if (
                    event.get("generation_id") != active["generation_id"]
                    or event.get("session_id") != current_session
                    or event.get("pid") != current_pid
                    or float(event.get("at", 0)) < float(active["activated_at"])
                ):
                    continue
                if event.get("hard_floor_ok") is False:
                    return self._rollback_locked(
                        "Iter recorded a completed-cycle hard health-floor failure"
                    )
                completion_proofs.append({
                    "heartbeat_id": event["heartbeat_id"],
                    "cycle": int(event.get("cycle", -1)),
                    "at": float(event.get("at", 0)),
                    "source": "immutable_completion",
                    "witness_heartbeat_id": event["heartbeat_id"],
                })

            heartbeat_id = heartbeat.get("heartbeat_id")
            if heartbeat.get("phase") == "cycle_complete" and heartbeat_id:
                completion_proofs.append({
                    "heartbeat_id": heartbeat_id,
                    "cycle": int(heartbeat.get("cycle", -1)),
                    "at": heartbeat_at,
                    "source": "latest_heartbeat",
                    "witness_heartbeat_id": heartbeat_id,
                })

            parent = candidate.get("activation_parent_heartbeat") or {}
            same_activation_process = bool(
                current_session
                and current_session == parent.get("session_id")
                and current_pid == parent.get("pid")
            )
            if same_activation_process:
                first_candidate_cycle = int(parent.get("cycle", -1)) + 1
                current_cycle = int(heartbeat.get("cycle", -1))
                last_completed_cycle = current_cycle - 1
                if heartbeat.get("phase") == "cycle_complete":
                    last_completed_cycle = current_cycle
                for completed_cycle in range(
                    first_candidate_cycle, last_completed_cycle + 1
                ):
                    inferred_id = "%s:%s:cycle_complete" % (
                        current_session, completed_cycle,
                    )
                    completion_proofs.append({
                        "heartbeat_id": inferred_id,
                        "cycle": completed_cycle,
                        "at": heartbeat_at,
                        "source": "successor_cycle",
                        "witness_heartbeat_id": heartbeat_id,
                    })

            unique_proofs = {}
            source_priority = {
                "immutable_completion": 0,
                "latest_heartbeat": 1,
                "successor_cycle": 2,
            }
            for proof in completion_proofs:
                existing = unique_proofs.get(proof["heartbeat_id"])
                if (
                    existing is None
                    or source_priority[proof["source"]]
                    < source_priority[existing["source"]]
                ):
                    unique_proofs[proof["heartbeat_id"]] = proof
            completion_proofs = sorted(
                unique_proofs.values(),
                key=lambda proof: (proof["cycle"], proof["heartbeat_id"]),
            )
            observed = candidate.setdefault("observed_heartbeats", [])
            completion_evidence = candidate.setdefault("completion_evidence", [])
            required = int(active["required_heartbeats"])
            for proof in completion_proofs:
                if len(observed) >= required:
                    break
                if proof["heartbeat_id"] in observed:
                    continue
                observed.append(proof["heartbeat_id"])
                completion_evidence.append(proof)
                candidate["last_heartbeat_at"] = proof["at"]
                self._write_candidate(candidate)
                self._append_event("probation_heartbeat_observed", {
                    "candidate_id": candidate["candidate_id"],
                    "heartbeat_id": proof["heartbeat_id"],
                    "count": len(observed),
                    "source": proof["source"],
                    "witness_heartbeat_id": proof["witness_heartbeat_id"],
                })
                try:
                    self._track_candidate(
                        candidate, "REC-1", "Externally supervise candidate probation",
                        "Observed %d of %d required distinct completed-cycle heartbeats; live Electron smoke remains bounded to this probation."
                        % (len(observed), active["required_heartbeats"]),
                        "Observe the next distinct completed cycle or promote when the required count is reached.",
                        "heartbeat-%s" % len(observed),
                    )
                except Exception as exc:
                    return self._rollback_locked("PWQ Tracking failed during probation: %s" % exc)
            if len(observed) < required:
                return {
                    "action": "waiting",
                    "reason": (
                        "probation heartbeats %d/%d"
                        % (len(observed), active["required_heartbeats"])
                        if completion_proofs
                        else "cycle has not completed"
                    ),
                    "active": active,
                }
            if candidate.get("fitness_before"):
                from .revision_fitness import fitness_snapshot, fitness_compare, record_outcome
                after = fitness_snapshot(self.iter_root)
                comparison = fitness_compare(candidate["fitness_before"], after)
                candidate["fitness_result"] = {"post_snapshot": after, "comparison": comparison}
                self._write_candidate(candidate)
                degraded = comparison["delta_composite"] < 0
                revert = candidate["contract"]["fitness_review"]["revert_on_degradation"]
                if degraded and revert:
                    recovered = self._rollback_locked("fitness degraded (delta=%s)" % comparison["delta_composite"])
                    try:
                        record_outcome(self.iter_root, self._generation_path(candidate["generation_id"]),
                                       candidate, "reverted", _atomic_json)
                    except (OSError, ValueError) as exc:
                        recovered["recording_error"] = str(exc)
                    return recovered
            candidate["status"] = "promoted"
            candidate["promoted_at"] = observed_at
            self._write_candidate(candidate)
            pointer = {
                "schema_version": SCHEMA_VERSION,
                "generation_id": active["generation_id"],
                "previous_generation_id": active["previous_generation_id"],
                "status": "stable",
                "candidate_id": candidate["candidate_id"],
                "activated_at": active["activated_at"],
                "promoted_at": observed_at,
            }
            _atomic_json(self.active_path, pointer)
            self._append_event("candidate_promoted", {
                "candidate_id": candidate["candidate_id"],
                "generation_id": active["generation_id"],
                "observed_heartbeats": len(observed),
            })
            if candidate.get("fitness_result"):
                try:
                    record_outcome(self.iter_root, self._generation_path(candidate["generation_id"]),
                                   candidate, "accepted", _atomic_json)
                except (OSError, ValueError) as exc:
                    # Reporting cannot undo healthy code; the candidate retains
                    # the actual measurements even if the old summary is unwritable.
                    self._append_event("fitness_recording_unavailable", {
                        "candidate_id": candidate["candidate_id"], "error": str(exc),
                    })
            try:
                self._track_candidate(
                    candidate, "HOT-2", "Promote an externally verified immutable generation",
                    "All %d required completed-cycle heartbeats were observed externally; the parent remains retained for recovery."
                    % len(observed),
                    "Continue normal operation and complete the PWQ item only after its broader acceptance evidence is reviewed.",
                    "promoted",
                )
            except Exception as exc:
                return self._rollback_stable_locked("PWQ Tracking failed at promotion: %s" % exc)
            return {"action": "promoted", "active": pointer, "candidate": candidate}

    def status(self):
        with self._locked():
            active = self._bootstrap_locked()
            self._verify_generation(active["generation_id"])
            events = self._events()
            ledger_tail_incomplete = self._last_ledger_tail_incomplete
            records = []
            for path in sorted(self.candidates_dir.glob("candidate-*.json")):
                value = _read_json(path)
                if isinstance(value, dict):
                    records.append(value)
            actionable = [
                value for value in records
                if value.get("status") in (
                    "quarantined", "validation_failed", "validated", "probation",
                )
            ]
            if active.get("candidate_id"):
                candidate = self._read_candidate(active["candidate_id"])
            elif len(actionable) == 1:
                candidate = actionable[0]
            else:
                candidate = None
            return {
                "schema_version": SCHEMA_VERSION,
                "active": active,
                "candidate": candidate,
                "candidate_count": len(records),
                "actionable_candidate_ids": [
                    value.get("candidate_id") for value in actionable
                ],
                "managed_roots": list(MANAGED_ROOTS),
                "fixed_tests": list(FIXED_TESTS),
                "heartbeat_path": str(self.heartbeat_path),
                "event_count": len(events),
                "last_event_hash": events[-1]["event_hash"] if events else "GENESIS",
                "ledger_tail_incomplete": ledger_tail_incomplete,
            }


class IterHeartbeat:
    """Atomic progress evidence written by Iter and judged externally."""

    def __init__(self, iter_root, session_id, pid=None):
        self.iter_root = Path(iter_root).resolve()
        self.path = self.iter_root / ".runtime" / "recovery" / "iter_heartbeat.json"
        self.completions_dir = (
            self.iter_root / ".runtime" / "recovery" / "cycle_completions"
        )
        self.session_id = session_id
        self.pid = int(pid if pid is not None else os.getpid())
        self.sequence = 0

    def write(self, generation_id, phase, cycle, hard_floor_ok=True, detail=""):
        self.sequence += 1
        value = {
            "schema_version": SCHEMA_VERSION,
            "heartbeat_id": "%s:%s:%s" % (self.session_id, cycle, phase),
            "session_id": self.session_id,
            "pid": self.pid,
            "sequence": self.sequence,
            "cycle": int(cycle),
            "generation_id": generation_id,
            "phase": phase,
            "hard_floor_ok": bool(hard_floor_ok),
            "detail": str(detail)[:1000],
            "at": time.time(),
        }
        _atomic_json(self.path, value)
        if phase == "cycle_complete":
            evidence = dict(value)
            evidence["event_hash"] = _sha256_bytes(
                _canonical(evidence).encode("utf-8")
            )
            evidence_path = self.completions_dir / (
                _sha256_bytes(value["heartbeat_id"].encode("utf-8")) + ".json"
            )
            if evidence_path.exists():
                existing = _read_json(evidence_path)
                if existing != evidence:
                    raise HotloadError(
                        "completed-cycle evidence changed for %s"
                        % value["heartbeat_id"]
                    )
            else:
                _atomic_json(evidence_path, evidence)
        return value
