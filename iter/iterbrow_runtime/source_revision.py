"""Host-owned source installation artifacts and crash-recoverable replacement.

Not a cognitive ledger, approval authority, supervisor or Iter tool. The host
injects an authentic verifier, quiesces affected processes and owns restart.
Every operation retains exact parent bytes and refuses unrelated worktree edits.
"""
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import uuid


ROOT_FILES = frozenset({"main.js", "preload.js", "package.json", "package-lock.json"})
ITER_FILES = frozenset({"iter.py", "metta_server.py", "metta_query_worker.py", "hotload_control.py",
    "state_manifest.json", "prompt.txt", "reprogramming.txt", "AGENTS.md", "requirements.txt",
    "pyproject.toml", "uv.lock"})
SOURCE_ROOTS = ("bridge/", "renderer/", "tests/", "scripts/", "docs/",
    "iter/iterbrow_runtime/", "iter/tools/", "iter/transformations/", "iter/channels/", "iter/seeds/")
SUFFIXES = frozenset({".py", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".jsx", ".json", ".html",
    ".css", ".svg", ".metta", ".md", ".sh", ".yml", ".yaml", ".toml", ".txt", ".lock"})
FORBIDDEN = frozenset({"private", "memory", "data", "node_modules", "chroma_db", "__pycache__"})
SECRET_FILES = frozenset({"settings.json", "credentials.json", "secrets.json", "oauth_tokens.json"})
GOVERNANCE_FIELDS = frozenset({"parent_revision", "parent_ruleset", "candidate_ruleset",
    "protected_registry_digest", "snapshot", "author_id", "parent_work_proposal_id"})
SHA = re.compile(r"^[a-f0-9]{64}$")
ID = re.compile(r"^source-[a-f0-9]{64}$")


class SourceRevisionError(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash(raw):
    return None if raw is None else hashlib.sha256(raw).hexdigest()


def _fsync(path):
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic(path, raw, mode=0o600):
    missing = []
    ancestor = path.parent
    while not ancestor.exists():
        missing.append(ancestor)
        ancestor = ancestor.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    for directory in reversed(missing):
        _fsync(directory)
        _fsync(directory.parent)
    temporary = path.with_name("." + path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _json(path, value):
    _atomic(path, (_canonical(value) + "\n").encode())


def _source_path(relative):
    if (not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative
            or str(PurePosixPath(relative)) != relative or PurePosixPath(relative).is_absolute()):
        raise SourceRevisionError("source path must be explicit canonical repository-relative text")
    parts = PurePosixPath(relative).parts
    if any(part in ("", ".", "..") or part.startswith(".") or part in FORBIDDEN or part in SECRET_FILES for part in parts):
        raise SourceRevisionError("source path names state, credentials, generated content or traversal")
    allowed = relative in ROOT_FILES or (len(parts) == 2 and parts[0] == "iter" and parts[1] in ITER_FILES)
    if not allowed:
        allowed = any(relative.startswith(prefix) for prefix in SOURCE_ROOTS) and PurePosixPath(relative).suffix in SUFFIXES
    if not allowed:
        raise SourceRevisionError("path is outside the source-only platform artifact surface")
    return relative


class SourceRevisionManager:
    def __init__(self, repository_root, *, verifier=None):
        self.root = Path(repository_root).resolve()
        self.verifier = verifier
        self.runtime = self._safe(self.root / "iter" / ".runtime" / "platform_revisions")
        self.candidates = self.runtime / "candidates"
        self.journal = self.runtime / "installation.json"
        self.history = self.runtime / "history"
        for directory in (self.candidates, self.history):
            self._safe(directory).mkdir(parents=True, exist_ok=True)

    def _safe(self, path):
        if not path.is_relative_to(self.root):
            raise SourceRevisionError("path escaped canonical repository")
        relative = path.relative_to(self.root)
        for length in range(1, len(relative.parts) + 1):
            if self.root.joinpath(*relative.parts[:length]).is_symlink():
                raise SourceRevisionError("source or artifact path contains a symlink")
        if not path.resolve().is_relative_to(self.root):
            raise SourceRevisionError("path escaped canonical repository")
        return path

    @contextmanager
    def _locked(self):
        with self._safe(self.runtime / "activation.lock").open("a+") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _live(self, relative):
        path = self._safe(self.root / _source_path(relative))
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
            raise SourceRevisionError("source is not a bounded regular file")
        return path.read_bytes()

    def _candidate_dir(self, candidate_id):
        if not isinstance(candidate_id, str) or not ID.fullmatch(candidate_id):
            raise SourceRevisionError("invalid immutable source candidate identity")
        return self._safe(self.candidates / candidate_id)

    def stage(self, changes, expected_base_hashes, governance=None, parent_manifest=None):
        if not isinstance(changes, dict) or not changes or len(changes) > 256:
            raise SourceRevisionError("changes must be a bounded explicit source path map")
        if not isinstance(expected_base_hashes, dict) or set(changes) != set(expected_base_hashes):
            raise SourceRevisionError("every source change requires its exact expected base hash")
        if governance is not None and (not isinstance(governance, dict) or set(governance) != GOVERNANCE_FIELDS):
            raise SourceRevisionError("governor metadata must match the current verifier schema")
        if parent_manifest is not None:
            if not isinstance(parent_manifest, dict) or not all(key in parent_manifest for key in ("source_hashes", "ruleset", "revision", "snapshot")):
                raise SourceRevisionError("frozen parent manifest lacks protected source/ruleset/revision/snapshot identity")
            parent_manifest = json.loads(_canonical(parent_manifest))
            if parent_manifest["ruleset"] != _hash(_canonical(parent_manifest["source_hashes"]).encode()):
                raise SourceRevisionError("frozen parent ruleset differs from its protected source manifest")
            changed_bases = parent_manifest.setdefault("changed_source_hashes", dict(expected_base_hashes))
            if changed_bases != expected_base_hashes:
                raise SourceRevisionError("frozen changed-source bases differ from requested source artifact")
        after, before, modes = {}, {}, {}
        with self._locked():
            if parent_manifest is not None:
                for relative, expected in parent_manifest["source_hashes"].items():
                    if _hash(self._live(relative)) != expected:
                        raise SourceRevisionError("frozen protected source parent drifted before staging: " + relative)
            for relative, supplied in sorted(changes.items()):
                _source_path(relative)
                if supplied is not None and not isinstance(supplied, (str, bytes)):
                    raise SourceRevisionError("source artifacts must be bytes, text or explicit deletion")
                raw = supplied.encode("utf-8") if isinstance(supplied, str) else supplied
                if raw is not None and len(raw) > 16 * 1024 * 1024:
                    raise SourceRevisionError("individual source artifact exceeds bounded file size")
                expected = expected_base_hashes[relative]
                if expected is not None and (not isinstance(expected, str) or not SHA.fullmatch(expected)):
                    raise SourceRevisionError("expected base hashes must be SHA256 or explicit absence")
                prior = self._live(relative)
                if _hash(prior) != expected:
                    raise SourceRevisionError("worktree conflict before staging: " + relative)
                if raw == prior:
                    raise SourceRevisionError("source manifest contains an unchanged path: " + relative)
                after[relative], before[relative] = raw, prior
                modes[relative] = stat.S_IMODE((self.root / relative).stat().st_mode) if prior is not None else None
            if sum(len(raw or b"") for raw in (*after.values(), *before.values())) > 64 * 1024 * 1024:
                raise SourceRevisionError("source artifact exceeds bounded staging size")
            body = {"schema_version": 1, "base_hashes": {p: _hash(v) for p, v in before.items()},
                "source_hashes": {p: _hash(v) for p, v in after.items()}, "base_modes": modes,
                "governance": governance, "parent_manifest": parent_manifest}
            candidate_id = "source-" + _hash(_canonical(body).encode())
            destination = self._candidate_dir(candidate_id)
            if destination.exists():
                return self.manifest(candidate_id)
            temporary = self._safe(self.candidates / (".stage-" + uuid.uuid4().hex))
            temporary.mkdir()
            try:
                for label, artifacts in (("before", before), ("after", after)):
                    for relative, raw in artifacts.items():
                        if raw is not None:
                            _atomic(temporary / label / relative, raw, 0o400)
                _json(temporary / "manifest.json", {"candidate_id": candidate_id, **body})
                os.replace(temporary, destination)
                _fsync(destination.parent)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
            return self.manifest(candidate_id)

    def manifest(self, candidate_id):
        directory = self._candidate_dir(candidate_id)
        manifest = json.loads(self._safe(directory / "manifest.json").read_text())
        body = {key: value for key, value in manifest.items() if key != "candidate_id"}
        if manifest.get("candidate_id") != candidate_id or candidate_id != "source-" + _hash(_canonical(body).encode()):
            raise SourceRevisionError("immutable source manifest identity mismatch")
        expected_files = {"manifest.json"}
        for label, key in (("before", "base_hashes"), ("after", "source_hashes")):
            for relative, expected in manifest[key].items():
                _source_path(relative)
                path = self._safe(directory / label / relative)
                raw = path.read_bytes() if path.is_file() else None
                if _hash(raw) != expected:
                    raise SourceRevisionError("immutable source artifact hash mismatch: " + relative)
                if expected is not None:
                    expected_files.add(label + "/" + relative)
        expected_directories = set()
        for name in expected_files:
            expected_directories.update(str(parent) for parent in PurePosixPath(name).parents if str(parent) != ".")
        actual_files, actual_directories = set(), set()
        for path in directory.rglob("*"):
            self._safe(path)
            if path.is_file():
                actual_files.add(path.relative_to(directory).as_posix())
            elif path.is_dir():
                actual_directories.add(path.relative_to(directory).as_posix())
            else:
                raise SourceRevisionError("artifact contains a non-regular entry")
        if actual_files != expected_files or actual_directories != expected_directories:
            raise SourceRevisionError("immutable source artifact contains unlisted entries")
        return manifest

    def candidate_reader(self, candidate_id):
        manifest = self.manifest(candidate_id)
        if manifest["governance"] is None:
            raise SourceRevisionError("candidate has no governor-change envelope")
        return {"candidate_id": candidate_id, "source_hashes": manifest["source_hashes"],
                "base_hashes": manifest["base_hashes"], **manifest["governance"]}

    def parent_reader(self, candidate_id):
        """Frozen source provenance, not permission to reuse obsolete authority."""
        manifest = self.manifest(candidate_id)
        if manifest.get("parent_manifest") is None:
            raise SourceRevisionError("source candidate has no frozen parent manifest")
        return manifest["parent_manifest"]

    def artifact_reader(self, candidate_id, relative):
        manifest = self.manifest(candidate_id)
        if relative not in manifest["source_hashes"]:
            raise SourceRevisionError("unlisted source artifact requested")
        raw = None if manifest["source_hashes"][relative] is None else self._safe(self._candidate_dir(candidate_id) / "after" / relative).read_bytes()
        if _hash(raw) != manifest["source_hashes"][relative]:
            raise SourceRevisionError("source artifact changed while being read")
        return raw

    def retained_parent_reader(self, candidate_id, relative):
        manifest = self.manifest(candidate_id)
        if relative not in manifest["base_hashes"]:
            raise SourceRevisionError("unlisted source parent requested")
        raw = None if manifest["base_hashes"][relative] is None else self._safe(self._candidate_dir(candidate_id) / "before" / relative).read_bytes()
        if _hash(raw) != manifest["base_hashes"][relative]:
            raise SourceRevisionError("retained source parent changed while being read")
        return raw

    def _authorize(self, candidate_id, operation, request):
        if not callable(self.verifier):
            raise SourceRevisionError("host-authenticated source verifier is required")
        receipt = self.verifier(candidate_id, operation, request)
        receipt = asdict(receipt) if is_dataclass(receipt) else receipt
        if not isinstance(receipt, dict) or receipt.get("candidate_id") != candidate_id:
            raise SourceRevisionError("source verifier returned no exact candidate receipt")
        return json.loads(_canonical(receipt))

    def _read_journal(self):
        path = self._safe(self.journal)
        if not path.exists():
            return None
        value = json.loads(path.read_text())
        if (not isinstance(value, dict) or value.get("schema_version") != 1
                or not ID.fullmatch(str(value.get("candidate_id", "")))
                or not re.fullmatch(r"[a-f0-9]{32}", str(value.get("operation_id", "")))
                or value.get("phase") not in ("applying", "applied", "restoring", "restored")
                or not isinstance(value.get("completed"), list) or len(value["completed"]) > 256):
            raise SourceRevisionError("source installation journal is invalid")
        for relative in value["completed"]:
            _source_path(relative)
        return value

    def _progress(self, value):
        _json(self._safe(self.journal), value)
        if value["phase"] in ("applied", "restored"):
            _json(self._safe(self.history / (value["operation_id"] + ".json")), value)

    def _replace(self, relative, raw, mode, expected_hashes):
        if _hash(self._live(relative)) not in expected_hashes:
            raise SourceRevisionError("worktree conflict during source replacement: " + relative)
        target = self._safe(self.root / relative)
        if raw is None:
            if target.exists():
                target.unlink()
                _fsync(target.parent)
        else:
            _atomic(target, raw, 0o644 if mode is None else mode)

    def apply(self, candidate_id, authorization_request):
        with self._locked():
            previous = self._read_journal()
            if previous and previous["phase"] in ("applying", "restoring"):
                raise SourceRevisionError("unfinished source replacement requires recovery first")
            manifest = self.manifest(candidate_id)
            receipt = self._authorize(candidate_id, "apply", authorization_request)
            for relative, expected in manifest["base_hashes"].items():
                if _hash(self._live(relative)) != expected:
                    raise SourceRevisionError("worktree conflict before source activation: " + relative)
                if expected is not None and stat.S_IMODE((self.root / relative).stat().st_mode) != manifest["base_modes"][relative]:
                    raise SourceRevisionError("worktree permission conflict before source activation: " + relative)
            journal = {"schema_version": 1, "candidate_id": candidate_id, "operation_id": uuid.uuid4().hex,
                       "phase": "applying", "completed": [], "verification_receipt": receipt}
            self._progress(journal)
            for relative in sorted(manifest["source_hashes"]):
                self._replace(relative, self.artifact_reader(candidate_id, relative), manifest["base_modes"][relative],
                              {manifest["base_hashes"][relative]})
                journal["completed"].append(relative)
                self._progress(journal)
            if any(_hash(self._live(path)) != sha for path, sha in manifest["source_hashes"].items()):
                raise SourceRevisionError("source changed before activation completion")
            journal["phase"] = "applied"
            self._progress(journal)
            return journal

    def _restore_locked(self, candidate_id, authorization_request):
        prior = self._read_journal()
        if not prior or prior["candidate_id"] != candidate_id or prior["phase"] == "restored":
            raise SourceRevisionError("candidate is not the current recoverable source installation")
        manifest = self.manifest(candidate_id)
        receipt = self._authorize(candidate_id, "restore", authorization_request)
        for relative in manifest["base_hashes"]:
            raw = self._live(relative)
            if _hash(raw) not in {manifest["base_hashes"][relative], manifest["source_hashes"][relative]}:
                raise SourceRevisionError("worktree conflict before retained-parent recovery: " + relative)
            expected_mode = manifest["base_modes"][relative]
            if raw is not None and stat.S_IMODE((self.root / relative).stat().st_mode) != (0o644 if expected_mode is None else expected_mode):
                raise SourceRevisionError("worktree permission conflict before retained-parent recovery: " + relative)
        journal = {**prior, "phase": "restoring", "completed": [], "restore_receipt": receipt}
        self._progress(journal)
        for relative in sorted(manifest["base_hashes"]):
            self._replace(relative, self.retained_parent_reader(candidate_id, relative), manifest["base_modes"][relative],
                          {manifest["base_hashes"][relative], manifest["source_hashes"][relative]})
            journal["completed"].append(relative)
            self._progress(journal)
        if any(_hash(self._live(path)) != sha for path, sha in manifest["base_hashes"].items()):
            raise SourceRevisionError("source changed before recovery completion")
        journal["phase"] = "restored"
        self._progress(journal)
        return journal

    def restore(self, candidate_id, authorization_request):
        with self._locked():
            return self._restore_locked(candidate_id, authorization_request)

    def recover(self, authorization_request):
        with self._locked():
            journal = self._read_journal()
            if not journal or journal["phase"] not in ("applying", "restoring"):
                return {"action": "none", "installation": journal}
            return {"action": "restored", "installation": self._restore_locked(journal["candidate_id"], authorization_request)}
