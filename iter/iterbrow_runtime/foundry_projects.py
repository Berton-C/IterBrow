"""User-owned application source projects; activation reuses APP-2.

The manifest is source metadata, not a cognitive/domain-state authority. App
records remain in app_contract's journal. Files under data/ are explicit exports
only. Draft source never changes an active immutable app revision.
"""

from __future__ import annotations

import fcntl
import json
import re
from contextlib import contextmanager
from pathlib import Path

from .app_revision_manager import (
    AppRevisionError, AppRevisionManager, FIXED_TESTS, MAX_TEXT_BYTES, MAX_FILES,
    _atomic_json, _atomic_text, _canonical, _sha256, _safe_relative,
)


APP_ID = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
SOURCE_DIRS = ("src", "tests", "migrations")


def source_relative(value):
    if (not isinstance(value, str) or not value or "\\" in value or "\x00" in value
            or value.startswith("/") or any(part in ("", ".", "..") for part in value.split("/"))):
        raise AppRevisionError("source path is not canonical or would traverse parents")
    return value


def source_files(files):
    """Source storage is language-neutral; APP-2 separately validates artifacts."""
    if not isinstance(files, dict) or len(files) > MAX_FILES:
        raise AppRevisionError("source update must be a bounded path-to-text object")
    result = {}
    for name, content in files.items():
        name = source_relative(name)
        if not isinstance(content, str):
            raise AppRevisionError("source must be UTF-8 text")
        result[name] = content
    if sum(len(content.encode("utf-8")) for content in result.values()) > MAX_TEXT_BYTES:
        raise AppRevisionError("source update exceeds bounded text limit")
    return result


def project_id(value):
    if not isinstance(value, str) or not APP_ID.fullmatch(value) or value == "crm":
        raise AppRevisionError("invalid or reserved foundry project id")
    return value


def no_symlinks(path, root):
    """Reject aliases before resolve; neither metadata nor source may escape."""
    path, root = Path(path), Path(root)
    if not path.is_relative_to(root):
        raise AppRevisionError("project path escapes its root")
    for candidate in (root, *[root / Path(*path.relative_to(root).parts[:i])
                              for i in range(1, len(path.relative_to(root).parts) + 1)]):
        if candidate.is_symlink():
            raise AppRevisionError("project path contains a symlink")
    if not path.resolve().is_relative_to(root.resolve()):
        raise AppRevisionError("project path escapes its root")
    return path


def load_project_manifest(iter_root, app_id):
    app_id = project_id(app_id)
    root = Path(iter_root).resolve()
    project = no_symlinks(root / "apps" / app_id, root)
    path = no_symlinks(project / "app.json", root)
    if not path.is_file():
        raise AppRevisionError("unsupported application scope: unregistered project %s" % app_id)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1 or manifest.get("app_id") != app_id
            or manifest.get("entrypoint") != "index.html"
            or manifest.get("source_dir") != "src"
            or manifest.get("state_owner") != "application_contract"):
        raise AppRevisionError("invalid foundry project manifest")
    return manifest


class FoundryProjects:
    def __init__(self, iter_root, *, revision_manager=None):
        self.iter_root = Path(iter_root).resolve()
        self.projects_root = no_symlinks(self.iter_root / "apps", self.iter_root)
        canonical_revisions = no_symlinks(self.iter_root / ".runtime" / "app_revisions", self.iter_root)
        self.revisions = revision_manager or AppRevisionManager(self.iter_root)
        if (Path(self.revisions.iter_root).resolve() != self.iter_root
                or Path(self.revisions.runtime_dir).resolve() != canonical_revisions.resolve()):
            raise AppRevisionError("project adapter must use the canonical app revision authority")
        self.projects_root.mkdir(parents=True, exist_ok=True)

    def _path(self, app_id):
        return no_symlinks(self.projects_root / project_id(app_id), self.iter_root)

    @contextmanager
    def _locked(self):
        path = no_symlinks(self.projects_root / ".writer.lock", self.iter_root)
        with path.open("a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _blueprint(value):
        if not isinstance(value, dict):
            raise AppRevisionError("blueprint must be an object")
        result = json.loads(_canonical(value))
        for name in ("title", "intention"):
            if not isinstance(result.get(name), str) or not result[name].strip():
                raise AppRevisionError("blueprint requires %s" % name)
        for name in ("invariants", "acceptance"):
            if (not isinstance(result.get(name), list) or not result[name]
                    or any(not isinstance(item, str) or not item.strip() for item in result[name])):
                raise AppRevisionError("blueprint requires nonempty %s" % name)
        if len(_canonical(result).encode()) > 65536:
            raise AppRevisionError("blueprint is too large")
        return result

    @staticmethod
    def _research(value):
        if not isinstance(value, list) or len(value) > 100:
            raise AppRevisionError("research must be a bounded list")
        for entry in value:
            if not isinstance(entry, dict) or not all(
                isinstance(entry.get(field), str) and entry[field].strip()
                for field in ("url", "retrieved_at", "license", "adopted_pattern")
            ):
                raise AppRevisionError("research needs URL, retrieval date, license and adopted pattern")
            if not entry["url"].startswith("https://"):
                raise AppRevisionError("research source must use HTTPS")
        if len(_canonical(value).encode()) > 262144:
            raise AppRevisionError("research metadata is too large")
        return json.loads(_canonical(value))

    def create(self, app_id, blueprint, research=None, provenance=None):
        app_id = project_id(app_id)
        blueprint, research = self._blueprint(blueprint), self._research(research or [])
        with self._locked():
            project = self._path(app_id)
            if project.exists():
                raise AppRevisionError("project already exists; revise it with an observed context hash")
            project.mkdir()
            for directory in (*SOURCE_DIRS, "data", "history"):
                (project / directory).mkdir()
            _atomic_json(project / "blueprint.json", blueprint)
            _atomic_json(project / "research.json", research)
            _atomic_json(project / "app.json", {
                "schema_version": 1, "app_id": app_id, "title": blueprint["title"],
                "entrypoint": "index.html", "source_dir": "src",
                "state_owner": "application_contract", "data_dir_role": "export-projection-only",
            })
            # Fixed empty host baseline is not a user app and never certifies one.
            self.revisions.ensure_baseline(app_id)
            return self._checkpoint(app_id, "created", provenance)

    def _inspect(self, app_id):
        manifest = load_project_manifest(self.iter_root, app_id)
        project = self._path(app_id)
        hashes = {}
        size = 0
        source_count = 0
        for name in ("app.json", "blueprint.json", "research.json"):
            path = no_symlinks(project / name, self.iter_root)
            hashes[name] = _sha256(path.read_bytes())
        for directory in SOURCE_DIRS:
            root = no_symlinks(project / directory, self.iter_root)
            for path in sorted(root.rglob("*")):
                no_symlinks(path, self.iter_root)
                if path.is_file():
                    content = path.read_bytes()
                    size += len(content)
                    source_count += 1
                    if source_count > MAX_FILES * 3 or size > MAX_TEXT_BYTES * 3:
                        raise AppRevisionError("project source exceeds bounded factory limits")
                    hashes[path.relative_to(project).as_posix()] = _sha256(content)
        return {
            "app_id": app_id, "project_path": str(project), "manifest": manifest,
            "source_context_hash": _sha256(_canonical(hashes)), "file_hashes": hashes,
            "blueprint": json.loads((project / "blueprint.json").read_text()),
            "research": json.loads((project / "research.json").read_text()),
        }

    def inspect(self, app_id):
        with self._locked():
            return self._inspect(app_id)

    def _checkpoint(self, app_id, operation, provenance=None):
        context = self._inspect(app_id)
        project = self._path(app_id)
        history = no_symlinks(project / "history" / (context["source_context_hash"] + ".json"), self.iter_root)
        if not history.exists():
            _atomic_json(history, {
                **context, "operation": operation, "provenance": provenance,
                "source_snapshot": {name: no_symlinks(project / name, self.iter_root).read_text(encoding="utf-8")
                                    for name in context["file_hashes"]},
            })
        return context

    def _expect(self, app_id, expected_context_hash):
        current = self._inspect(app_id)
        if not expected_context_hash or current["source_context_hash"] != expected_context_hash:
            raise AppRevisionError("stale project context; reread before modifying or staging")
        return current

    def write_source(self, app_id, files, expected_context_hash, *, directory="src", provenance=None, deletions=None):
        if directory not in SOURCE_DIRS:
            raise AppRevisionError("only source, tests and migrations may be edited")
        # Preserve arbitrary user-owned code. Only the separate APP-2 artifact
        # staging lane limits renderable bundle types; this is not a platform
        # restriction on Python tools, language sources or other build outputs.
        normalised = source_files(files)
        deletions = [source_relative(value) for value in (deletions or [])]
        if not normalised and not deletions:
            raise AppRevisionError("source update must contain writes or deletions")
        if set(normalised).intersection(deletions):
            raise AppRevisionError("source update cannot write and delete the same path")
        with self._locked():
            current = self._expect(app_id, expected_context_hash)
            root = no_symlinks(self._path(app_id) / directory, self.iter_root)
            remaining = {name[len(directory)+1:]: (self._path(app_id) / name).stat().st_size
                         for name in current["file_hashes"] if name.startswith(directory + "/")}
            for name in deletions:
                path = no_symlinks(root / name, self.iter_root)
                if not path.is_file():
                    raise AppRevisionError("deleted source must be an existing file")
                remaining.pop(name, None)
            remaining.update({name: len(content.encode("utf-8")) for name, content in normalised.items()})
            if len(remaining) > MAX_FILES or sum(remaining.values()) > MAX_TEXT_BYTES:
                raise AppRevisionError("source update exceeds bounded bundle limits")
            for relative, content in normalised.items():
                path = no_symlinks(root / relative, self.iter_root)
                path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_text(path, content)
            for relative in deletions:
                no_symlinks(root / relative, self.iter_root).unlink()
            return self._checkpoint(app_id, "write:" + directory, provenance)

    def revise_blueprint(self, app_id, blueprint, expected_context_hash, provenance=None):
        blueprint = self._blueprint(blueprint)
        with self._locked():
            context = self._expect(app_id, expected_context_hash)
            _atomic_json(self._path(app_id) / "blueprint.json", blueprint)
            _atomic_json(self._path(app_id) / "app.json", {**context["manifest"], "title": blueprint["title"]})
            return self._checkpoint(app_id, "blueprint", provenance)

    def record_research(self, app_id, research, expected_context_hash, provenance=None):
        research = self._research(research)
        with self._locked():
            context = self._expect(app_id, expected_context_hash)
            merged = {entry["url"]: entry for entry in context["research"]}
            merged.update({entry["url"]: entry for entry in research})
            _atomic_json(self._path(app_id) / "research.json", self._research(list(merged.values())))
            return self._checkpoint(app_id, "research", provenance)

    def stage(self, app_id, expected_context_hash, purpose, source_pressure, provenance, artifact_files=None):
        with self._locked():
            context = self._expect(app_id, expected_context_hash)
            root = self._path(app_id) / "src"
            mapping = artifact_files if artifact_files is not None else {
                name[4:]: name[4:] for name in context["file_hashes"] if name.startswith("src/")
            }
            if not isinstance(mapping, dict) or not mapping:
                raise AppRevisionError("renderer artifact mapping must be a nonempty object")
            mapping = {str(_safe_relative(output)): source_relative(source) for output, source in mapping.items()}
            if any("src/" + source not in context["file_hashes"] for source in mapping.values()):
                raise AppRevisionError("renderer artifact must map observed project source files")
            files = {output: no_symlinks(root / source, self.iter_root).read_text(encoding="utf-8")
                     for output, source in mapping.items()}
            if any(_sha256(files[output]) != context["file_hashes"]["src/" + source] for output, source in mapping.items()):
                raise AppRevisionError("source changed while reading candidate")
            self._expect(app_id, expected_context_hash)
            active = self.revisions.status(app_id)["active"]
            return self.revisions.stage(app_id, files, {
                "version": 1, "purpose": purpose, "source_pressure": source_pressure,
                "atlas_slice": "APP-2", "entrypoint": "index.html",
                "allowed_files": sorted(files), "tests": list(FIXED_TESTS),
                "rollback_target": active["revision_id"],
                "provenance": {"source": provenance, "source_context_hash": expected_context_hash},
            })

    def list_projects(self):
        with self._locked():
            return [self._inspect(path.name) for path in sorted(self.projects_root.iterdir())
                    if APP_ID.fullmatch(path.name) and (path / "app.json").exists()]

    def export_data(self, app_id, read_context):
        """Caller supplies existing trusted APP-1 reader; export is never loaded as truth."""
        with self._locked():
            load_project_manifest(self.iter_root, app_id)
            context = read_context(app_id)
            if not isinstance(context, dict) or context.get("app_id") != app_id:
                raise AppRevisionError("domain export identity mismatch")
            target = no_symlinks(self._path(app_id) / "data" / "export.json", self.iter_root)
            _atomic_json(target, {"role": "export-projection-only", "context": context})
            return {"path": str(target), "sha256": _sha256(target.read_bytes())}
