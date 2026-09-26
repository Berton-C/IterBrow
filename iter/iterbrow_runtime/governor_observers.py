"""Host-configured, source-bound subprocess observations for GOV-SELF-1.

There are deliberately NO production recipes installed by this module. A host
must register independently reviewed harnesses with distinct obligations and
isolated, complete parent/candidate source workspaces. Exit status authenticates
that harness execution, not arbitrary child JSON or the meaning of a test suite.
This process boundary is NOT an OS security sandbox; that remains host-owned.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import signal
import subprocess
import tempfile
import time

from .cognitive_fabric import digest
from .governor_change import PROOF_KINDS
from .governor_records import TrustedObserver


class ObserverRecipeError(RuntimeError):
    pass


def _sha(raw):
    return None if raw is None else hashlib.sha256(raw).hexdigest()


def _captured(stream):
    stream.seek(0)
    hashed, length, tail = hashlib.sha256(), 0, b""
    while True:
        chunk = stream.read(65536)
        if not chunk:
            break
        hashed.update(chunk)
        length += len(chunk)
        tail = (tail + chunk)[-2000:]
    return {"sha256": hashed.hexdigest(), "bytes": length, "tail": tail.decode("utf-8", "replace")}


@dataclass(frozen=True)
class ObserverRecipe:
    kind: str
    argv: tuple
    candidate_root: object
    candidate_sources: dict
    harness_sources: dict  # absolute host-trusted harness paths -> pinned SHA256
    scope: str
    parent_root: object = None
    parent_sources: object = None
    timeout: float = 30
    max_output_bytes: int = 1024 * 1024


def missing_production_recipes():
    """Inspected reusable components, not four fabricated production proofs."""
    return {
        "shadow": {"ready": False, "reusable": ["tests/test_governor_records.py"],
            "missing": "fixed-case parent-versus-exact-candidate native decision comparison; current tests prove native capture, not that comparison"},
        "counterexamples": {"ready": False, "reusable": ["tests/test_governor_change.py", "tests/test_engineering_alignment.py"],
            "missing": "host-owned adversarial case runner bound to both exact source workspaces; existing cases are component fixtures"},
        "restart": {"ready": False, "reusable": ["tests/test_metta_service.py", "tests/test_source_governor_handoff.py"],
            "missing": "exact-candidate cold-process service launch, persisted-state replay and native query proof; metta_service uses fake engines and handoff is a fixture"},
        "rollback": {"ready": False, "reusable": ["tests/test_source_revision.py", "tests/test_source_governor_handoff.py"],
            "missing": "exact-candidate failure and independent source/activation/memory restoration rehearsal under an approved host lifecycle recipe"},
    }


def _workspace(root, hashes):
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir() or not isinstance(hashes, dict) or not hashes:
        raise ObserverRecipeError("observer workspace/manifest is unavailable")
    expected = set()
    for relative, expected_hash in hashes.items():
        path = PurePosixPath(relative)
        if (not isinstance(relative, str) or str(path) != relative or path.is_absolute()
                or ".." in path.parts or "\\" in relative):
            raise ObserverRecipeError("observer source manifest path is not canonical")
        target = root / relative
        for length in range(1, len(path.parts) + 1):
            if root.joinpath(*path.parts[:length]).is_symlink():
                raise ObserverRecipeError("observer source path contains a symlink")
        raw = target.read_bytes() if target.is_file() else None
        if _sha(raw) != expected_hash:
            raise ObserverRecipeError("observer workspace source hash differs: " + relative)
        if raw is not None:
            expected.add(relative)
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ObserverRecipeError("observer workspace contains a symlink")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise ObserverRecipeError("observer workspace contains unbound source files")
    return root.resolve()


class GovernorObserverRunner:
    def __init__(self, *, recipes, candidate_reader, artifact_reader, parent_reader):
        if not isinstance(recipes, dict) or set(recipes) - set(PROOF_KINDS):
            raise ObserverRecipeError("unknown observer obligation")
        self.recipes = deepcopy(recipes)
        signatures = set()
        for kind, recipe in self.recipes.items():
            if (not isinstance(recipe, ObserverRecipe) or recipe.kind != kind or not recipe.scope
                    or not isinstance(recipe.argv, tuple) or len(recipe.argv) < 2
                    or not all(isinstance(value, str) and value for value in recipe.argv)
                    or not Path(recipe.argv[0]).is_absolute()
                    or Path(recipe.argv[0]).name in {"sh", "bash", "zsh", "fish", "cmd", "powershell"}
                    or not 0 < recipe.timeout <= 300 or not 1024 <= recipe.max_output_bytes <= 4 * 1024 * 1024):
                raise ObserverRecipeError("invalid bounded host observer recipe")
            if not recipe.harness_sources or not any(arg in recipe.harness_sources for arg in recipe.argv[1:]):
                raise ObserverRecipeError("observer command lacks an explicitly pinned independent harness")
            if recipe.argv in signatures:
                raise ObserverRecipeError("one command cannot be relabelled as different proof obligations")
            signatures.add(recipe.argv)
            if kind == "shadow" and (recipe.parent_root is None or recipe.parent_sources is None):
                raise ObserverRecipeError("shadow recipe requires both parent and candidate source workspaces")
        self.candidate_reader, self.artifact_reader, self.parent_reader = candidate_reader, artifact_reader, parent_reader

    def as_observers(self):
        # Incomplete configuration remains incomplete; GovernorRecords requires
        # all four explicit registrations rather than inventing missing passes.
        return {kind: TrustedObserver("platform.subprocess_observer." + kind,
            lambda context, kind=kind: self.observe(kind, context)) for kind in self.recipes}

    def _binding(self, recipe, context):
        candidate = self.candidate_reader(context["candidate"]["candidate_id"])
        parent = self.parent_reader()
        if candidate != context["candidate"] or parent != context["parent"]:
            raise ObserverRecipeError("observer candidate or frozen parent differs")
        expected_candidate = {**parent["source_hashes"], **parent.get("changed_source_hashes", {})}
        expected_candidate.update(candidate["source_hashes"])
        if any(recipe.candidate_sources.get(path) != value for path, value in expected_candidate.items()):
            raise ObserverRecipeError("recipe workspace does not bind the complete candidate delta")
        for path, expected in candidate["source_hashes"].items():
            if _sha(self.artifact_reader(candidate["candidate_id"], path)) != expected:
                raise ObserverRecipeError("candidate artifact changed")
        root = _workspace(recipe.candidate_root, recipe.candidate_sources)
        if recipe.parent_root is not None:
            expected_parent = {**parent["source_hashes"], **parent.get("changed_source_hashes", {})}
            if any(recipe.parent_sources.get(path) != value for path, value in expected_parent.items()):
                raise ObserverRecipeError("recipe does not bind the complete parent sources")
            _workspace(recipe.parent_root, recipe.parent_sources)
        for supplied, expected in recipe.harness_sources.items():
            path = Path(supplied)
            if not path.is_absolute() or path.is_symlink() or not path.is_file() or _sha(path.read_bytes()) != expected:
                raise ObserverRecipeError("independent observer harness changed")
            if path.resolve().is_relative_to(root):
                raise ObserverRecipeError("candidate cannot provide its own acceptance harness")
        return {"candidate_digest": digest(candidate), "parent_digest": digest(parent),
                "workspace_digest": digest(recipe.candidate_sources), "harness_digest": digest(recipe.harness_sources)}

    def observe(self, kind, context):
        recipe = self.recipes[kind]
        base = {"recipe_kind": kind, "recipe_scope": recipe.scope, "argv": list(recipe.argv),
                "candidate_id": context["candidate"]["candidate_id"], "child_json_used_as_verdict": False}
        try:
            before = self._binding(recipe, context)
        except (ObserverRecipeError, OSError, ValueError) as exc:
            return {**base, "status": "unknown", "process_state": "not_started", "detail": str(exc)}
        started = time.monotonic()
        process = None
        stopped = None
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                process = subprocess.Popen(recipe.argv, cwd=str(recipe.candidate_root), shell=False,
                    stdout=out, stderr=err, start_new_session=True,
                    env={"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
                         "PYTHONPATH": str(Path(recipe.candidate_root) / "iter"), "ITER_DIR": str(Path(recipe.candidate_root) / "iter")})
                while process.poll() is None:
                    if time.monotonic() - started > recipe.timeout:
                        stopped = "timed_out"
                        break
                    if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > recipe.max_output_bytes:
                        stopped = "output_limit"
                        break
                    time.sleep(0.01)
            except OSError as exc:
                return {**base, **before, "status": "unknown", "process_state": "not_started", "detail": str(exc)}
            finally:
                if process is not None:
                    # Kill any remaining descendants too; the recipe cannot leave
                    # background work running after an observation completes.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
            stdout, stderr = _captured(out), _captured(err)
        if stdout["bytes"] + stderr["bytes"] > recipe.max_output_bytes:
            stopped = "output_limit"
        observed = {**base, **before, "process_state": stopped or "exited", "exit_code": process.returncode,
            "elapsed_seconds": time.monotonic() - started, "stdout_sha256": stdout["sha256"], "stderr_sha256": stderr["sha256"],
            "stdout_bytes": stdout["bytes"], "stderr_bytes": stderr["bytes"],
            "output_truncated": stopped == "output_limit", "stdout_tail": stdout["tail"], "stderr_tail": stderr["tail"]}
        try:
            after = self._binding(recipe, context)
            if after != before:
                raise ObserverRecipeError("observer source binding changed during execution")
        except (ObserverRecipeError, OSError, ValueError) as exc:
            return {**observed, "status": "unknown", "detail": str(exc)}
        return {**observed, "status": "unknown" if stopped else "passed" if process.returncode == 0 else "failed"}
