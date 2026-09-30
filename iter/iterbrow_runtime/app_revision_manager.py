"""Content-addressed, recoverable revisions for IterBrow tab/app bundles.

This service is deliberately separate from ``hotload_manager``.  Python
component generations and renderer application bundles have different load
and health boundaries.  Application candidates remain inert in quarantine;
only the Electron-side supervisor may supply visible-load and APP-1 context
evidence or promote a probation revision.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .pwq_protocol import HOTLOAD_GUARDIAN_PROOF, PWQStore


SCHEMA_VERSION = 1
SUPPORTED_APPS = {"crm": "crm/index.html"}
EMPTY_PROJECT_BASELINE = """<!doctype html><html><body><main>Application not activated</main><script>
window.iterApp.appContext().then(() => { document.body.dataset.iterReady = 'true'; });
</script></body></html>\n"""
FIXED_TESTS = (
    "bundle_integrity",
    "entrypoint_contract",
    "network_membrane",
)
ALLOWED_SUFFIXES = {".html", ".css", ".js", ".json", ".svg"}
MAX_FILES = 128
MAX_TEXT_BYTES = 2 * 1024 * 1024
NETWORK_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bfetch\s*\(", re.IGNORECASE),
    re.compile(r"\bXMLHttpRequest\b"),
    re.compile(r"\bWebSocket\s*\(", re.IGNORECASE),
    re.compile(r"\bEventSource\s*\(", re.IGNORECASE),
    re.compile(r"\bsendBeacon\s*\(", re.IGNORECASE),
)


class AppRevisionError(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
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


def _safe_app_id(app_id):
    value = str(app_id or "")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", value):
        raise AppRevisionError("unsupported application scope: %s" % value)
    return value


def _safe_relative(path):
    raw = str(path or "")
    if not raw or "\\" in raw or "\x00" in raw or any(part in ("", ".", "..") for part in raw.split("/")):
        raise AppRevisionError("application path is not canonical or would traverse parents")
    value = Path(raw)
    if value.is_absolute() or not value.parts or ".." in value.parts:
        raise AppRevisionError("application path must be relative and cannot traverse parents")
    if any(part in ("", ".") for part in value.parts):
        raise AppRevisionError("application path is not canonical")
    if value.suffix.lower() not in ALLOWED_SUFFIXES:
        raise AppRevisionError("unsupported application file type: %s" % value)
    if value.name == "bundle.json":
        raise AppRevisionError("bundle.json is reserved platform metadata")
    return value


class AppRevisionManager:
    def __init__(self, iter_root, runtime_dir=None, pwq_store=None):
        self.iter_root = Path(iter_root).resolve()
        self.runtime_dir = Path(
            runtime_dir or self.iter_root / ".runtime" / "app_revisions"
        )
        self.apps_dir = self.runtime_dir / "apps"
        self.candidates_dir = self.runtime_dir / "candidates"
        self.pointers_dir = self.runtime_dir / "pointers"
        self.events_path = self.runtime_dir / "events.jsonl"
        self.lock_path = self.runtime_dir / "writer.lock"
        self.pwq_store = pwq_store or PWQStore(
            self.iter_root / ".runtime" / "pwq",
            self.iter_root / ".runtime" / "pwq.json",
        )
        self.apps_dir.mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.pointers_dir.mkdir(parents=True, exist_ok=True)

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
        events = []
        previous = "GENESIS"
        incomplete_tail_hash = None
        if self.events_path.exists():
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
                        incomplete_tail_hash = _sha256(raw_line)
                        break
                    raise AppRevisionError(
                        "application revision event ledger is corrupt at line %d" % (index + 1)
                    ) from exc
                supplied = event.pop("event_hash", None)
                actual = _sha256(_canonical(event))
                if (
                    supplied != actual
                    or event.get("previous_hash") != previous
                    or event.get("sequence") != len(events) + 1
                ):
                    raise AppRevisionError(
                        "application revision event hash chain mismatch at line %d" % (index + 1)
                    )
                event["event_hash"] = supplied
                events.append(event)
                previous = supplied
        if incomplete_tail_hash:
            _atomic_text(
                self.events_path,
                "".join(_canonical(event) + "\n" for event in events),
            )
            recovery = {
                "schema_version": SCHEMA_VERSION,
                "sequence": len(events) + 1,
                "event_id": str(uuid.uuid4()),
                "kind": "ledger_tail_recovered",
                "at": time.time(),
                "payload": {
                    "discarded_tail_sha256": incomplete_tail_hash,
                    "recovered_event_count": len(events),
                },
                "previous_hash": previous,
            }
            recovery["event_hash"] = _sha256(_canonical(recovery))
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(_canonical(recovery) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            events.append(recovery)
            previous = recovery["event_hash"]
        event = {
            "schema_version": SCHEMA_VERSION,
            "sequence": len(events) + 1,
            "event_id": str(uuid.uuid4()),
            "kind": kind,
            "at": time.time(),
            "payload": payload,
            "previous_hash": previous,
        }
        event["event_hash"] = _sha256(_canonical(event))
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(event) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(self.events_path.parent)
        return event

    def _pointer_path(self, app_id):
        return self.pointers_dir / (self._registered_id(app_id) + ".json")

    def _registered_id(self, app_id):
        app_id = _safe_app_id(app_id)
        if app_id not in SUPPORTED_APPS:
            # Registration persists in the existing deployment pointer. Broken
            # editable source metadata must never strand a healthy immutable app
            # or prevent its rollback. New identities still require a manifest.
            pointer = _read_json(self.pointers_dir / (app_id + ".json"))
            if pointer and pointer.get("app_id") == app_id:
                return app_id
            from .foundry_projects import load_project_manifest
            load_project_manifest(self.iter_root, app_id)
        return app_id

    def registered_apps(self):
        from .foundry_projects import APP_ID, load_project_manifest, no_symlinks
        result = [app_id for app_id, source in SUPPORTED_APPS.items()
                  if (self.iter_root / source).is_file() or (self.pointers_dir / (app_id + ".json")).exists()]
        for path in sorted(self.pointers_dir.glob("*.json")):
            if APP_ID.fullmatch(path.stem) and path.stem not in result:
                pointer = _read_json(path)
                if pointer and pointer.get("app_id") == path.stem:
                    result.append(path.stem)
        root = no_symlinks(self.iter_root / "apps", self.iter_root)
        if root.exists():
            for project in sorted(root.iterdir()):
                if APP_ID.fullmatch(project.name) and (project / "app.json").exists():
                    if project.name not in result:
                        try:
                            load_project_manifest(self.iter_root, project.name)
                        except (AppRevisionError, ValueError):
                            continue  # Malformed inactive draft is not a runnable app.
                        result.append(project.name)
        return result

    def _baseline_files(self, app_id):
        self._registered_id(app_id)
        if app_id not in SUPPORTED_APPS:
            # New app source must pass the same quarantine as every revision.
            return {"index.html": EMPTY_PROJECT_BASELINE}
        source = self.iter_root / SUPPORTED_APPS[app_id]
        if not source.is_file() or source.is_symlink():
            raise AppRevisionError("application source entrypoint is missing or aliased: %s" % source)
        return {"index.html": source.read_text(encoding="utf-8")}

    def _candidate_path(self, candidate_id):
        if not re.fullmatch(r"appcandidate-[a-f0-9]{32}", str(candidate_id)):
            raise AppRevisionError("invalid application candidate id")
        return self.candidates_dir / (str(candidate_id) + ".json")

    def _bundle_path(self, app_id, revision_id):
        if not re.fullmatch(r"apprev-[a-f0-9]{64}", str(revision_id)):
            raise AppRevisionError("invalid application revision id")
        from .foundry_projects import no_symlinks
        return no_symlinks(self.apps_dir / self._registered_id(app_id) / "bundles" / str(revision_id), self.runtime_dir)

    def _read_candidate(self, candidate_id):
        value = _read_json(self._candidate_path(candidate_id))
        if not value:
            raise AppRevisionError("application candidate does not exist")
        return value

    def _write_candidate(self, candidate):
        _atomic_json(self._candidate_path(candidate["candidate_id"]), candidate)

    @staticmethod
    def _normalise_files(files):
        if not isinstance(files, dict) or not files:
            raise AppRevisionError("application files must be a non-empty path-to-text object")
        if len(files) > MAX_FILES:
            raise AppRevisionError("application bundle exceeds the fixed file-count limit")
        normalised = {}
        size = 0
        for supplied, content in files.items():
            relative = _safe_relative(supplied).as_posix()
            if not isinstance(content, str):
                raise AppRevisionError("application candidate files must be UTF-8 text")
            encoded = content.encode("utf-8")
            size += len(encoded)
            normalised[relative] = content
        if size > MAX_TEXT_BYTES:
            raise AppRevisionError("application bundle exceeds the fixed text-size limit")
        return normalised

    @staticmethod
    def _file_hashes(files):
        return {path: _sha256(content) for path, content in sorted(files.items())}

    def _write_bundle(self, app_id, files, origin, parent_revision_id=None):
        hashes = self._file_hashes(files)
        bundle_hash = _sha256(_canonical(hashes))
        revision_id = "apprev-" + bundle_hash
        destination = self._bundle_path(app_id, revision_id)
        if destination.exists():
            manifest = self._verify_bundle(app_id, revision_id, bundle_hash)
            return destination, manifest
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / ("." + revision_id + ".tmp-" + uuid.uuid4().hex)
        temporary.mkdir(parents=True)
        try:
            for relative, content in sorted(files.items()):
                target = temporary / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x", encoding="utf-8") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "app_id": app_id,
                "revision_id": revision_id,
                "bundle_hash": bundle_hash,
                "file_hashes": hashes,
                "entrypoint": "index.html",
                "origin": origin,
                "parent_revision_id": parent_revision_id,
                "created_at": time.time(),
            }
            _atomic_json(temporary / "bundle.json", manifest)
            os.replace(str(temporary), str(destination))
            _fsync_directory(destination.parent)
            return destination, manifest
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def _verify_bundle(self, app_id, revision_id, expected_hash=None):
        path = self._bundle_path(app_id, revision_id)
        manifest = _read_json(path / "bundle.json")
        if not manifest:
            raise AppRevisionError("application bundle manifest is missing")
        expected_files = manifest.get("file_hashes") or {}
        actual_files = {}
        for candidate in sorted(path.rglob("*")):
            if candidate.is_symlink():
                raise AppRevisionError("application bundle contains a symlink")
            if not candidate.is_file() or candidate.name == "bundle.json":
                continue
            relative = candidate.relative_to(path).as_posix()
            actual_files[relative] = _sha256(candidate.read_bytes())
        actual_hash = _sha256(_canonical(actual_files))
        if actual_files != expected_files or actual_hash != manifest.get("bundle_hash"):
            raise AppRevisionError("application bundle hash mismatch")
        if expected_hash and actual_hash != expected_hash:
            raise AppRevisionError("application bundle hash does not match candidate")
        if manifest.get("revision_id") != "apprev-" + actual_hash:
            raise AppRevisionError("application revision identity does not match bundle hash")
        return manifest

    def _pointer(self, app_id):
        value = _read_json(self._pointer_path(app_id))
        if not value:
            raise AppRevisionError("application has no active revision pointer")
        return value

    def ensure_baseline(self, app_id):
        app_id = _safe_app_id(app_id)
        with self._locked():
            existing = _read_json(self._pointer_path(app_id))
            if existing:
                self._verify_bundle(app_id, existing["revision_id"])
                return existing
            files = self._baseline_files(app_id)
            _path, manifest = self._write_bundle(app_id, files, "source_baseline")
            pointer = {
                "schema_version": SCHEMA_VERSION,
                "app_id": app_id,
                "revision_id": manifest["revision_id"],
                "bundle_hash": manifest["bundle_hash"],
                "entrypoint": manifest["entrypoint"],
                "previous_revision_id": None,
                "status": "stable",
                "candidate_id": None,
                "activated_at": time.time(),
            }
            _atomic_json(self._pointer_path(app_id), pointer)
            self._append_event("baseline_created", {
                "app_id": app_id,
                "revision_id": pointer["revision_id"],
                "bundle_hash": pointer["bundle_hash"],
            })
            return pointer

    def _normalise_contract(self, contract, app_id, files, parent_revision_id):
        if not isinstance(contract, dict):
            raise AppRevisionError("application revision contract must be an object")
        required = (
            "version", "purpose", "source_pressure",
            "entrypoint", "allowed_files", "tests", "rollback_target",
            "provenance",
        )
        missing = [field for field in required if field not in contract]
        if missing:
            raise AppRevisionError("application revision contract is missing: %s" % ", ".join(missing))
        if contract["entrypoint"] != "index.html" or "index.html" not in files:
            raise AppRevisionError("v1 application entrypoint must be index.html")
        if sorted(contract["allowed_files"]) != sorted(files):
            raise AppRevisionError("allowed_files must exactly match staged files")
        if set(contract["tests"]) != set(FIXED_TESTS):
            raise AppRevisionError("candidate-defined validation is not allowed")
        if contract["rollback_target"] != parent_revision_id:
            raise AppRevisionError("rollback_target must name the exact active parent revision")
        result = {field: contract[field] for field in required}
        if "atlas_slice" in contract:
            result["atlas_slice"] = contract["atlas_slice"]
        result["app_id"] = app_id
        return result

    def stage(self, app_id, files, contract):
        app_id = _safe_app_id(app_id)
        normalised = self._normalise_files(files)
        with self._locked():
            if not _read_json(self._pointer_path(app_id)):
                raise AppRevisionError("application baseline must be initialized before staging")
            active = self._pointer(app_id)
            if active["status"] != "stable":
                raise AppRevisionError("cannot stage while the application is in probation")
            canonical_contract = self._normalise_contract(
                contract, app_id, normalised, active["revision_id"]
            )
            bundle, manifest = self._write_bundle(
                app_id, normalised, "quarantined_candidate", active["revision_id"]
            )
            candidate = {
                "schema_version": SCHEMA_VERSION,
                "candidate_id": "appcandidate-" + uuid.uuid4().hex,
                "app_id": app_id,
                "revision_id": manifest["revision_id"],
                "bundle_hash": manifest["bundle_hash"],
                "bundle_path": str(bundle),
                "parent_revision_id": active["revision_id"],
                "status": "quarantined",
                "contract": canonical_contract,
                "validation": None,
                "authorization": None,
                "observations": [],
                "created_at": time.time(),
            }
            self._write_candidate(candidate)
            self._append_event("candidate_staged", {
                "candidate_id": candidate["candidate_id"],
                "app_id": app_id,
                "revision_id": candidate["revision_id"],
                "parent_revision_id": candidate["parent_revision_id"],
                "bundle_hash": candidate["bundle_hash"],
            })
            return candidate

    def validate(self, candidate_id):
        with self._locked():
            candidate = self._read_candidate(candidate_id)
            if candidate["status"] not in ("quarantined", "validation_failed", "validated"):
                raise AppRevisionError("candidate cannot be validated from %s" % candidate["status"])
            manifest = self._verify_bundle(
                candidate["app_id"], candidate["revision_id"], candidate["bundle_hash"]
            )
            bundle = self._bundle_path(candidate["app_id"], candidate["revision_id"])
            entrypoint = bundle / manifest["entrypoint"]
            source = entrypoint.read_text(encoding="utf-8") if entrypoint.is_file() else ""
            results = []
            integrity_ok = bool(manifest.get("file_hashes")) and entrypoint.is_file()
            results.append({
                "test": "bundle_integrity", "passed": integrity_ok,
                "detail": "content hashes and exact file set verified" if integrity_ok else "entrypoint missing",
            })
            contract_ok = (
                "window.iterApp" in source
                and ".appContext" in source
                and "dataset.iterReady" in source
            )
            results.append({
                "test": "entrypoint_contract", "passed": contract_ok,
                "detail": (
                    "APP-1 context and visible readiness handshake declared"
                    if contract_ok else
                    "entrypoint must use window.iterApp.appContext and set dataset.iterReady"
                ),
            })
            network_hits = []
            for relative in sorted(manifest["file_hashes"]):
                text = (bundle / relative).read_text(encoding="utf-8")
                for pattern in NETWORK_PATTERNS:
                    if pattern.search(text):
                        network_hits.append("%s:%s" % (relative, pattern.pattern))
            network_ok = not network_hits
            results.append({
                "test": "network_membrane", "passed": network_ok,
                "detail": "no direct network primitive" if network_ok else "; ".join(network_hits),
            })
            passed = all(result["passed"] for result in results)
            candidate["status"] = "validated" if passed else "validation_failed"
            candidate["validation"] = {
                "at": time.time(),
                "passed": passed,
                "fixed_tests": list(FIXED_TESTS),
                "results": results,
                "candidate_executed": False,
            }
            self._write_candidate(candidate)
            self._append_event(
                "candidate_validated" if passed else "candidate_validation_failed",
                {"candidate_id": candidate_id, "passed": passed},
            )
            return candidate

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
            "action": "app_revision.activate",
            "app_id": candidate["app_id"],
            "candidate_id": candidate["candidate_id"],
            "revision_id": candidate["revision_id"],
            "bundle_hash": candidate["bundle_hash"],
            "rollback_target": candidate["parent_revision_id"],
        }

    def propose_candidate(self, candidate_id, proposal_id=None):
        with self._locked():
            candidate = self._read_candidate(candidate_id)
            if candidate.get("status") != "validated" or not (
                    candidate.get("validation") or {}).get("passed"):
                raise AppRevisionError("candidate must pass fixed validation before proposal")
            proposal_id = proposal_id or "app-revision:" + candidate_id
            board = self.pwq_store.command(
                "propose", proposal_id, actor="iter",
                payload={
                    "title": "Activate %s application revision" % candidate["app_id"].upper(),
                    "ask": "Approve exact immutable app bundle for external probation",
                    "work_class": "build",
                    "governance_refs": {
                        "atlas_slices": ["APP-2", "REC-1"],
                        "invariants": ["INV-15", "INV-21", "INV-32", "INV-33"],
                    },
                    "approval_policy": self.split_approval_policy(),
                    "authorization_scope": self.candidate_authorization_scope(candidate),
                },
                command_id="propose:" + candidate_id,
            )
            candidate["proposal_id"] = proposal_id
            self._write_candidate(candidate)
            return board

    def attest_candidate(self, candidate_id, proposal_id):
        with self._locked():
            candidate = self._read_candidate(candidate_id)
            validation = candidate.get("validation") or {}
            if candidate.get("status") != "validated" or not validation.get("passed"):
                raise AppRevisionError("candidate must pass fixed validation before guardian attestation")
            if validation.get("candidate_executed") is not False:
                raise AppRevisionError("application validation must remain non-executing")
            active = self._pointer(candidate["app_id"])
            if active.get("status") != "stable" or active.get("revision_id") != candidate.get("parent_revision_id"):
                raise AppRevisionError("candidate rollback parent is no longer the stable revision")
            self._verify_bundle(candidate["app_id"], candidate["revision_id"], candidate["bundle_hash"])
            board = self.pwq_store.read()
            item = next((entry for entry in board.get("items", []) if entry.get("id") == proposal_id), None)
            if not item:
                raise AppRevisionError("PWQ proposal does not exist")
            if item.get("authorization_scope") != self.candidate_authorization_scope(candidate):
                raise AppRevisionError("PWQ authorization scope does not bind this exact app candidate")
            eligible = (item.get("approval_policy") or {}).get("eligible_signers") or []
            if not any(
                signer.get("signer_id") == "platform:hotload_guardian"
                and signer.get("role") == "runtime_guardian"
                for signer in eligible
            ):
                raise AppRevisionError("PWQ proposal does not request the runtime guardian role")
            evidence = {
                "candidate_id": candidate_id,
                "app_id": candidate["app_id"],
                "revision_id": candidate["revision_id"],
                "bundle_hash": candidate["bundle_hash"],
                "parent_revision_id": candidate["parent_revision_id"],
                "fixed_tests": validation["fixed_tests"],
                "candidate_executed": validation["candidate_executed"],
                "proposal_digest": item.get("proposal_digest"),
            }
            return self.pwq_store.command(
                "sign", proposal_id, actor="platform.hotload_guardian",
                payload={
                    "signer_id": "platform:hotload_guardian",
                    "role": "runtime_guardian",
                    "proof": {
                        "type": HOTLOAD_GUARDIAN_PROOF,
                        "value": _sha256(_canonical(evidence)),
                    },
                },
                expected_version=item.get("proposal_version"),
                command_id="app-guardian:%s:v%s:%s" % (
                    candidate_id, item.get("proposal_version"), item.get("proposal_digest")
                ),
            )

    def _verify_authorization(self, candidate, proposal_id, dispatch_authorization):
        board = self.pwq_store.read()
        item = next((entry for entry in board.get("items", []) if entry.get("id") == proposal_id), None)
        if not item:
            raise AppRevisionError("PWQ proposal does not exist")
        if item.get("work_class") != "build":
            raise AppRevisionError("application activation requires build-class PWQ authority")
        if not self._scope_covers_revision(item.get("authorization_scope"), candidate):
            raise AppRevisionError("PWQ authorization is not bound to this exact app candidate")
        if not (item.get("approval_status") or {}).get("ready"):
            raise AppRevisionError("PWQ approval threshold and required roles are not satisfied")
        if item.get("status") not in ("approved", "in_progress"):
            raise AppRevisionError("PWQ proposal is not approved for application dispatch")
        if not dispatch_authorization or item.get("dispatch_authorization") != dispatch_authorization:
            raise AppRevisionError("current PWQ dispatch authorization is required")
        if item.get("status") == "approved":
            board = self.pwq_store.command(
                "start", proposal_id, actor="iter",
                payload={"dispatch_authorization": dispatch_authorization},
                expected_version=item.get("proposal_version"),
                command_id="dispatch:" + proposal_id + ":v" + str(item.get("proposal_version")),
            )
            item = next(entry for entry in board["items"] if entry.get("id") == proposal_id)
        return {
            "proposal_id": proposal_id,
            "proposal_version": item.get("proposal_version"),
            "proposal_digest": item.get("proposal_digest"),
            "dispatch_authorization": dispatch_authorization,
            "authorization_evidence_digest": item.get("authorization_evidence_digest"),
            "authorization_scope": item.get("authorization_scope"),
        }

    def _scope_covers_revision(self, scope, candidate):
        return (scope == self.candidate_authorization_scope(candidate) or
                scope == {"action": "app.revise", "app_id": candidate["app_id"]})

    def approved_revision_work(self, candidate, proposal_id=""):
        """Reuse one app-scoped consent without model-maintained certificates."""
        matches = [item for item in self.pwq_store.read().get("items", [])
                   if (not proposal_id or item.get("id") == proposal_id)
                   and item.get("work_class") == "build"
                   and item.get("status") in ("approved", "in_progress")
                   and (item.get("approval_status") or {}).get("ready")
                   and self._scope_covers_revision(item.get("authorization_scope"), candidate)]
        if len(matches) != 1:
            raise AppRevisionError("specify one current approved work item for this app")
        return matches[0]

    def _authorization_current(self, candidate):
        authorization = candidate.get("authorization") or {}
        if authorization.get("mode") == "ordinary_loop":
            return True
        board = self.pwq_store.read()
        item = next((entry for entry in board.get("items", [])
                     if entry.get("id") == authorization.get("proposal_id")), None)
        return bool(
            item
            and item.get("status") == "in_progress"
            and item.get("proposal_version") == authorization.get("proposal_version")
            and item.get("proposal_digest") == authorization.get("proposal_digest")
            and item.get("dispatch_authorization") == authorization.get("dispatch_authorization")
            and self._scope_covers_revision(item.get("authorization_scope"), candidate)
        )

    def _track_candidate(self, candidate, atlas_slice, bounded_claim,
                         evidence_open_gaps, next_trigger, command_suffix):
        # The board is a progress projection; recovery follows actual health and
        # current consent, never the availability of its reporting surface.
        if (candidate.get("authorization") or {}).get("mode") == "ordinary_loop":
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
                pass
            return warning

    def _report_candidate(self, candidate, atlas_slice, bounded_claim,
                          evidence_open_gaps, next_trigger, command_suffix):
        authorization = candidate.get("authorization") or {}
        proposal_id = authorization.get("proposal_id")
        if not proposal_id:
            raise AppRevisionError("application candidate has no PWQ authorization to track")
        invariants = ["INV-15", "INV-21", "INV-32", "INV-33"]
        return self.pwq_store.command(
            "track", proposal_id, actor="platform.recovery",
            payload={
                "target": "Recoverable tab/application revision",
                "atlas_slice": atlas_slice,
                "bounded_claim": bounded_claim,
                "invariants": invariants,
                "evidence_open_gaps": evidence_open_gaps,
                "boundaries": (
                    "PWQ binds the exact immutable bundle and rollback parent; the app "
                    "candidate cannot approve itself, report its own health, or promote itself."
                ),
                "next_trigger": next_trigger,
                "source_revision": str(candidate.get("contract", {}).get("provenance", "")),
            },
            expected_version=authorization.get("proposal_version"),
            command_id="app-tracking:%s:%s" % (
                candidate["candidate_id"], command_suffix
            ),
        )

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
            reusable_work = (authorization.get("authorization_scope") or {}).get("action") == "app.revise"
            if item and item.get("status") == "in_progress" and not reusable_work:
                board = self.pwq_store.command(
                    "pause", proposal_id, actor="platform.recovery",
                    payload={"reason": reason},
                    expected_version=item.get("proposal_version"),
                    command_id="app-recovery-pause:" + candidate["candidate_id"],
                )
                item = next(entry for entry in board["items"] if entry.get("id") == proposal_id)
            if item and (item.get("status") == "paused" or
                         (reusable_work and item.get("status") == "in_progress")):
                return self._track_candidate(
                    candidate, "REC-1",
                    "Restore the exact verified application parent after failed probation",
                    "Application rollback completed. Failure evidence: %s" % reason,
                    "Inspect failure evidence and repair within the existing work scope; ask if scope changes.",
                    "rollback",
                )
        except Exception as exc:
            return {"tracking_error": "%s: %s" % (type(exc).__name__, exc)}
        return None

    def activate(self, candidate_id, proposal_id="", dispatch_authorization="",
                 required_observations=1, observation_timeout=90):
        with self._locked():
            candidate = self._read_candidate(candidate_id)
            proposal_id = proposal_id or candidate.get("proposal_id", "")
            if proposal_id and not dispatch_authorization:
                work = self.approved_revision_work(candidate, proposal_id)
                proposal_id = work["id"]
                dispatch_authorization = work["dispatch_authorization"]
            active = self._pointer(candidate["app_id"])
            if active["status"] != "stable":
                raise AppRevisionError("another application revision is already in probation")
            if candidate.get("status") != "validated" or not (
                    candidate.get("validation") or {}).get("passed"):
                raise AppRevisionError("candidate must pass fixed validation before activation")
            if candidate["parent_revision_id"] != active["revision_id"]:
                raise AppRevisionError("candidate parent is no longer the active revision")
            self._verify_bundle(candidate["app_id"], candidate["revision_id"], candidate["bundle_hash"])
            if proposal_id or dispatch_authorization:
                authorization = self._verify_authorization(candidate, proposal_id, dispatch_authorization)
            else:
                authorization = {"mode": "ordinary_loop", "app_id": candidate["app_id"]}
            candidate["status"] = "probation"
            candidate["authorization"] = authorization
            candidate["activated_at"] = time.time()
            candidate["required_observations"] = max(1, min(int(required_observations), 10))
            candidate["observation_timeout"] = max(30.0, min(float(observation_timeout), 600.0))
            candidate["observations"] = []
            self._track_candidate(
                candidate, "APP-2", "Admit one immutable application bundle for probation",
                "Fixed inert checks passed; no renderer health observation has yet been admitted.",
                "Atomically activate the bundle, then require external load, visibility, and APP-1 context evidence.",
                "admitted",
            )
            self._write_candidate(candidate)
            pointer = {
                "schema_version": SCHEMA_VERSION,
                "app_id": candidate["app_id"],
                "revision_id": candidate["revision_id"],
                "bundle_hash": candidate["bundle_hash"],
                "entrypoint": candidate["contract"]["entrypoint"],
                "previous_revision_id": active["revision_id"],
                "status": "probation",
                "candidate_id": candidate_id,
                "activated_at": candidate["activated_at"],
                "required_observations": candidate["required_observations"],
                "observation_timeout": candidate["observation_timeout"],
            }
            _atomic_json(self._pointer_path(candidate["app_id"]), pointer)
            self._append_event("candidate_activated", {
                "candidate_id": candidate_id,
                "app_id": candidate["app_id"],
                "revision_id": candidate["revision_id"],
                "previous_revision_id": active["revision_id"],
                "proposal_id": proposal_id,
            })
            try:
                self._track_candidate(
                    candidate, "REC-1", "Externally supervise application probation",
                    "The candidate is active on probation with 0 of %d required external observations."
                    % candidate["required_observations"],
                    "Promote only after distinct Electron observations prove load, visible readiness, and APP-1 context.",
                    "activated",
                )
            except Exception as exc:
                recovered = self._rollback_probation_locked(
                    candidate["app_id"], "PWQ Tracking failed after app activation: %s" % exc
                )
                raise AppRevisionError(recovered["reason"])
            return pointer

    def _rollback_probation_locked(self, app_id, reason):
        active = self._pointer(app_id)
        if active.get("status") != "probation":
            return {"action": "none", "reason": "no application revision in probation", "active": active}
        candidate = self._read_candidate(active["candidate_id"])
        previous = active.get("previous_revision_id")
        previous_manifest = self._verify_bundle(app_id, previous)
        candidate["status"] = "rolled_back"
        candidate["rolled_back_at"] = time.time()
        candidate["rollback_reason"] = reason
        self._write_candidate(candidate)
        pointer = {
            "schema_version": SCHEMA_VERSION,
            "app_id": app_id,
            "revision_id": previous,
            "bundle_hash": previous_manifest["bundle_hash"],
            "entrypoint": previous_manifest["entrypoint"],
            "previous_revision_id": previous_manifest.get("parent_revision_id"),
            "status": "stable",
            "candidate_id": None,
            "activated_at": time.time(),
        }
        _atomic_json(self._pointer_path(app_id), pointer)
        self._append_event("candidate_rolled_back", {
            "candidate_id": candidate["candidate_id"],
            "failed_revision_id": candidate["revision_id"],
            "restored_revision_id": previous,
            "reason": reason,
        })
        tracking = self._pause_and_track_recovery(candidate, reason)
        result = {"action": "rolled_back", "reason": reason, "active": pointer, "candidate": candidate}
        if tracking and tracking.get("tracking_error"):
            result["tracking_error"] = tracking["tracking_error"]
        return result

    def _rollback_stable_locked(self, app_id, reason):
        active = self._pointer(app_id)
        previous = active.get("previous_revision_id")
        if active.get("status") != "stable" or not previous:
            raise AppRevisionError("stable application revision has no rollback target: %s" % reason)
        manifest = self._verify_bundle(app_id, previous)
        candidate = self._read_candidate(active["candidate_id"]) if active.get("candidate_id") else None
        if candidate:
            candidate["status"] = "rolled_back_after_promotion"
            candidate["rolled_back_at"] = time.time()
            candidate["rollback_reason"] = reason
            self._write_candidate(candidate)
        pointer = {
            "schema_version": SCHEMA_VERSION,
            "app_id": app_id,
            "revision_id": previous,
            "bundle_hash": manifest["bundle_hash"],
            "entrypoint": manifest["entrypoint"],
            "previous_revision_id": manifest.get("parent_revision_id"),
            "status": "stable",
            "candidate_id": None,
            "activated_at": time.time(),
        }
        _atomic_json(self._pointer_path(app_id), pointer)
        self._append_event("stable_revision_rolled_back", {
            "failed_revision_id": active["revision_id"],
            "restored_revision_id": previous,
            "reason": reason,
        })
        tracking = self._pause_and_track_recovery(candidate, reason) if candidate else None
        result = {"action": "rolled_back", "reason": reason, "active": pointer, "candidate": candidate}
        if tracking and tracking.get("tracking_error"):
            result["tracking_error"] = tracking["tracking_error"]
        return result

    def rollback_probation(self, app_id="crm", reason="external supervisor requested rollback"):
        app_id = _safe_app_id(app_id)
        with self._locked():
            return self._rollback_probation_locked(app_id, reason)

    def supervisor_report(self, app_id, revision_id, observation_id, *,
                          load_ok, visible_handshake, context_ok,
                          context_commit=None, detail=""):
        app_id = _safe_app_id(app_id)
        observation_id = str(observation_id or "").strip()
        if not observation_id:
            raise AppRevisionError("external observation identity is required")
        with self._locked():
            active = self._pointer(app_id)
            if active.get("status") != "probation":
                return {"action": "none", "reason": "no application revision in probation", "active": active}
            candidate = self._read_candidate(active["candidate_id"])
            if revision_id != active["revision_id"]:
                return self._rollback_probation_locked(app_id, "renderer reported the wrong application revision")
            try:
                self._verify_bundle(app_id, revision_id, candidate["bundle_hash"])
            except AppRevisionError as exc:
                return self._rollback_probation_locked(app_id, str(exc))
            if not self._authorization_current(candidate):
                return self._rollback_probation_locked(app_id, "PWQ authorization changed during app probation")
            if not (bool(load_ok) and bool(visible_handshake) and bool(context_ok)):
                return self._rollback_probation_locked(
                    app_id, detail or "application load, visible handshake, or APP-1 context proof failed"
                )
            if not isinstance(context_commit, int) or context_commit < 0:
                return self._rollback_probation_locked(app_id, "application context proof lacks a commit identity")
            existing = {entry["observation_id"] for entry in candidate.get("observations") or []}
            if observation_id not in existing:
                candidate.setdefault("observations", []).append({
                    "observation_id": observation_id,
                    "at": time.time(),
                    "revision_id": revision_id,
                    "load_ok": True,
                    "visible_handshake": True,
                    "context_ok": True,
                    "context_commit": context_commit,
                    "detail": str(detail or ""),
                })
                self._write_candidate(candidate)
                self._append_event("probation_observed", {
                    "candidate_id": candidate["candidate_id"],
                    "observation_id": observation_id,
                    "context_commit": context_commit,
                })
                try:
                    self._track_candidate(
                        candidate, "REC-1", "Externally supervise application probation",
                        "Observed %d of %d required distinct Electron health proofs; observation %s binds AtomSpace commit %d."
                        % (
                            len(candidate["observations"]),
                            candidate["required_observations"],
                            observation_id,
                            context_commit,
                        ),
                        "Observe another distinct proof or promote when the required count is reached.",
                        "observation-%d" % len(candidate["observations"]),
                    )
                except Exception as exc:
                    return self._rollback_probation_locked(
                        app_id, "PWQ Tracking failed during app probation: %s" % exc
                    )
            if len(candidate["observations"]) < candidate["required_observations"]:
                return {
                    "action": "waiting",
                    "observed": len(candidate["observations"]),
                    "required": candidate["required_observations"],
                    "active": active,
                }
            candidate["status"] = "promoted"
            candidate["promoted_at"] = time.time()
            self._write_candidate(candidate)
            pointer = {
                **active,
                "status": "stable",
                "promoted_at": candidate["promoted_at"],
            }
            _atomic_json(self._pointer_path(app_id), pointer)
            self._append_event("candidate_promoted", {
                "candidate_id": candidate["candidate_id"],
                "revision_id": revision_id,
                "observation_ids": [entry["observation_id"] for entry in candidate["observations"]],
            })
            try:
                self._track_candidate(
                    candidate, "APP-2", "Promote an externally verified application bundle",
                    "All %d required Electron health proofs passed with APP-1 context commits; the exact parent remains retained for recovery."
                    % len(candidate["observations"]),
                    "Continue normal operation and complete the PWQ item only after broader acceptance evidence is reviewed.",
                    "promoted",
                )
            except Exception as exc:
                return self._rollback_stable_locked(
                    app_id, "PWQ Tracking failed at app promotion: %s" % exc
                )
            return {"action": "promoted", "active": pointer, "candidate": candidate}

    def supervisor_check(self, app_id="crm", renderer_present=True, now=None):
        app_id = _safe_app_id(app_id)
        observed_at = float(now if now is not None else time.time())
        with self._locked():
            active = self._pointer(app_id)
            try:
                self._verify_bundle(app_id, active["revision_id"], active.get("bundle_hash"))
            except AppRevisionError as exc:
                if active.get("status") == "probation":
                    return self._rollback_probation_locked(app_id, str(exc))
                if active.get("previous_revision_id"):
                    return self._rollback_stable_locked(app_id, str(exc))
                raise
            if active.get("status") != "probation":
                return {"action": "none", "active": active}
            candidate = self._read_candidate(active["candidate_id"])
            if not self._authorization_current(candidate):
                return self._rollback_probation_locked(app_id, "PWQ authorization changed during app probation")
            elapsed = observed_at - float(active.get("activated_at") or observed_at)
            if elapsed > float(active.get("observation_timeout") or 90):
                return self._rollback_probation_locked(app_id, "application probation timed out")
            if not renderer_present and elapsed > 5:
                return self._rollback_probation_locked(app_id, "application renderer disappeared during probation")
            return {
                "action": "waiting",
                "observed": len(candidate.get("observations") or []),
                "required": candidate.get("required_observations", 1),
                "active": active,
            }

    def recover_on_startup(self, app_id="crm"):
        app_id = _safe_app_id(app_id)
        with self._locked():
            if not _read_json(self._pointer_path(app_id)):
                files = self._baseline_files(app_id)
                _bundle, manifest = self._write_bundle(app_id, files, "source_baseline")
                pointer = {
                    "schema_version": SCHEMA_VERSION,
                    "app_id": app_id,
                    "revision_id": manifest["revision_id"],
                    "bundle_hash": manifest["bundle_hash"],
                    "entrypoint": manifest["entrypoint"],
                    "previous_revision_id": None,
                    "status": "stable",
                    "candidate_id": None,
                    "activated_at": time.time(),
                }
                _atomic_json(self._pointer_path(app_id), pointer)
                self._append_event("baseline_created", {
                    "app_id": app_id,
                    "revision_id": pointer["revision_id"],
                    "bundle_hash": pointer["bundle_hash"],
                })
                return {"action": "initialized", "active": pointer, **self._resolved(pointer)}
            active = self._pointer(app_id)
            if active.get("status") == "probation":
                result = self._rollback_probation_locked(
                    app_id, "abandoned application probation recovered before tab restore"
                )
                return {**result, **self._resolved(result["active"])}
            try:
                self._verify_bundle(app_id, active["revision_id"], active.get("bundle_hash"))
            except AppRevisionError as exc:
                if active.get("previous_revision_id"):
                    result = self._rollback_stable_locked(app_id, str(exc))
                    return {**result, **self._resolved(result["active"])}
                raise
            return {"action": "none", "active": active, **self._resolved(active)}

    def _resolved(self, pointer):
        path = self._bundle_path(pointer["app_id"], pointer["revision_id"])
        return {
            "revision_id": pointer["revision_id"],
            "bundle_hash": pointer["bundle_hash"],
            "entrypoint_path": str(path / pointer["entrypoint"]),
        }

    def status(self, app_id="crm"):
        app_id = _safe_app_id(app_id)
        with self._locked():
            if not _read_json(self._pointer_path(app_id)):
                raise AppRevisionError("application baseline is not initialized")
            active = self._pointer(app_id)
            self._verify_bundle(app_id, active["revision_id"], active.get("bundle_hash"))
            candidates = []
            for path in sorted(self.candidates_dir.glob("appcandidate-*.json")):
                candidate = _read_json(path)
                if candidate and candidate.get("app_id") == app_id:
                    candidates.append(candidate)
            return {
                "schema_version": SCHEMA_VERSION,
                "storage_contract": {
                    "app_id": app_id,
                    "backend": "journaled AtomSpace application_contract",
                    "collections": "arbitrary valid identifiers; CRM_COLLECTIONS limits only legacy migration/projection",
                    "read": "window.iterApp.appContext()",
                    "write": "window.iterApp.appCommand(command)",
                    "inspect_wiring": "window.iterApp.storageStatus() in a reloaded registered app tab",
                    "proof": "Observe the intended value saved and reopened; code presence or a receipt alone is insufficient.",
                },
                "active": active,
                **self._resolved(active),
                "candidate": candidates[-1] if candidates else None,
                "actionable_candidate_ids": [
                    candidate["candidate_id"] for candidate in candidates
                    if candidate.get("status") in (
                        "quarantined", "validation_failed", "validated", "probation"
                    )
                ],
            }
