#!/usr/bin/env python3
"""State-safe lifecycle primitives for IterBrow's macOS installer.

This is deliberately not a second runtime supervisor.  It uses the existing
state manifest and AtomSpace RPC, and it runs only for an explicit installer
update, repair, or uninstall command.
"""

import argparse
import hashlib
import io
import json
import os
import shutil
import signal
import socket
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath


SCHEMA_VERSION = 1
METADATA_NAME = ".iterbrow_lifecycle.json"


def _safe_relative(value):
    path = PurePosixPath(str(value).replace("\\", "/"))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise RuntimeError("unsafe lifecycle path: %s" % value)
    return path


def _load_manifest(root):
    manifest_path = root / "iter" / "state_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("entries"), list):
        raise RuntimeError("state_manifest.json has an unsupported shape")
    return manifest, manifest_path


def _preserved_paths(root, include_tools=False):
    manifest, _ = _load_manifest(root)
    selected = []
    seen = set()
    for entry in manifest["entries"]:
        # Source seeds are versioned program inputs.  Every other declared path
        # is live state, a secret, a projection, or a reconstructable cache;
        # preserving all of them makes update exact while remaining manifest-
        # bounded.  Fresh code supplies the new source seeds.
        if entry.get("role") == "source_seed":
            continue
        rel = _safe_relative(PurePosixPath("iter") / _safe_relative(entry.get("path", "")))
        if rel in seen or not (root / Path(*rel.parts)).exists():
            continue
        seen.add(rel)
        selected.append(rel)

    # Older installs placed connector/user material at the repository-level
    # private boundary.  Preserve it without broadening capture to the repo.
    if (root / "private").exists():
        selected.append(PurePosixPath("private"))
    if include_tools and (root / "tools").exists():
        selected.append(PurePosixPath("tools"))
    return selected


def _tar_filter(info):
    # State snapshots contain ordinary files/directories only.  Refuse device,
    # FIFO, socket, and link entries so restore cannot escape its destination.
    if not (info.isfile() or info.isdir()):
        raise RuntimeError("refusing to snapshot a link or special file: %s" % info.name)
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def snapshot(root, archive, include_tools=False):
    root = root.resolve()
    archive = archive.expanduser().resolve()
    paths = _preserved_paths(root, include_tools=include_tools)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "created_at": int(time.time()),
        "paths": [str(path) for path in paths],
        "include_tools": bool(include_tools),
    }
    archive.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=archive.name + ".pending-", dir=str(archive.parent)
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with tarfile.open(temporary, "w:gz", format=tarfile.PAX_FORMAT) as bundle:
            payload = json.dumps(metadata, sort_keys=True).encode("utf-8")
            header = tarfile.TarInfo(METADATA_NAME)
            header.size = len(payload)
            header.mode = 0o600
            header.mtime = metadata["created_at"]
            bundle.addfile(header, io.BytesIO(payload))
            for rel in paths:
                bundle.add(root / Path(*rel.parts), arcname=str(rel), recursive=True, filter=_tar_filter)
        os.chmod(temporary, 0o600)
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    return {"archive": str(archive), "sha256": digest, "paths": metadata["paths"]}


def _validated_archive(bundle):
    try:
        metadata_member = bundle.getmember(METADATA_NAME)
    except KeyError as error:
        raise RuntimeError("lifecycle archive has no metadata") from error
    metadata = json.loads(bundle.extractfile(metadata_member).read().decode("utf-8"))
    if metadata.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("lifecycle archive schema is unsupported")
    allowed = [_safe_relative(value) for value in metadata.get("paths", [])]
    for member in bundle.getmembers():
        rel = _safe_relative(member.name)
        if member.name == METADATA_NAME:
            continue
        if not (member.isfile() or member.isdir()):
            raise RuntimeError("lifecycle archive contains a link or special file: %s" % member.name)
        if not any(rel == parent or parent in rel.parents for parent in allowed):
            raise RuntimeError("lifecycle archive contains an undeclared path: %s" % member.name)
    return metadata, allowed


def _extract_validated_archive(bundle, destination):
    """Extract the already-validated regular files without version-specific tar filters."""
    for member in bundle.getmembers():
        if member.name == METADATA_NAME:
            continue
        rel = _safe_relative(member.name)
        target = destination / Path(*rel.parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            os.chmod(target, member.mode & 0o777)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source = bundle.extractfile(member)
        if source is None:
            raise RuntimeError("lifecycle archive file could not be read: %s" % member.name)
        with source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
        os.chmod(target, member.mode & 0o777)
        os.utime(target, (member.mtime, member.mtime))


def restore(root, archive):
    root = root.resolve()
    archive = archive.expanduser().resolve()
    with tarfile.open(archive, "r:gz") as bundle:
        metadata, paths = _validated_archive(bundle)
        with tempfile.TemporaryDirectory(prefix="iterbrow-state-restore-") as temporary:
            extracted = Path(temporary)
            _extract_validated_archive(bundle, extracted)
            restored = []
            for rel in paths:
                source = extracted / Path(*rel.parts)
                if not source.exists():
                    continue
                destination = root / Path(*rel.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    if destination.is_dir():
                        shutil.rmtree(destination)
                    else:
                        destination.unlink()
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    shutil.copy2(source, destination)
                restored.append(str(rel))
    return {"archive": str(archive), "restored": restored, "metadata": metadata}


def _instance_socket(root, kind):
    instance = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:16]
    return Path("/tmp/iter-%s-%s.sock" % (kind, instance))


def _rpc(socket_path, method, timeout=4.0):
    request = (json.dumps({"method": method, "params": {}}) + "\n").encode("utf-8")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(socket_path))
        client.sendall(request)
        response = b""
        while b"\n" not in response:
            chunk = client.recv(65536)
            if not chunk:
                break
            response += chunk
    value = json.loads(response.split(b"\n", 1)[0].decode("utf-8"))
    if not value.get("ok"):
        raise RuntimeError(value.get("error") or "%s RPC failed" % method)
    return value.get("result")


def _process_alive(pid):
    try:
        os.kill(int(pid), 0)
        return int(pid) > 1
    except (OSError, TypeError, ValueError):
        return False


def _retire_verified_orphan_iter(root):
    heartbeat = root / "iter" / ".runtime" / "recovery" / "iter_heartbeat.json"
    try:
        pid = int(json.loads(heartbeat.read_text(encoding="utf-8")).get("pid"))
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    if not _process_alive(pid):
        return None
    command = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, check=False
    ).stdout.strip()
    cwd_output = subprocess.run(
        ["/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
        capture_output=True, text=True, check=False,
    ).stdout.splitlines()
    cwd_line = next((line[1:] for line in cwd_output if line.startswith("n")), "")
    if "iter.py" not in command or not cwd_line or Path(cwd_line).resolve() != (root / "iter").resolve():
        raise RuntimeError("refusing to stop an unverified process from a stale Iter heartbeat")
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 5
    while time.time() < deadline and _process_alive(pid):
        time.sleep(0.1)
    if _process_alive(pid):
        raise RuntimeError("verified Iter process did not stop for lifecycle operation")
    return pid


def prepare_offline(root):
    root = root.resolve()
    browser_socket = _instance_socket(root, "browser")
    if browser_socket.exists():
        try:
            _rpc(browser_socket, "getTabs", timeout=1.0)
        except Exception:
            pass
        else:
            raise RuntimeError("IterBrow is open; quit it before update, repair, or uninstall")
    retired = _retire_verified_orphan_iter(root)
    atomspace_socket = _instance_socket(root, "metta")
    checkpoint = None
    if atomspace_socket.exists():
        try:
            status = _rpc(atomspace_socket, "status")
        except Exception:
            status = None
        if status:
            expected = str((root / "iter").resolve())
            if str(Path(status.get("iter_dir", "")).resolve()) != expected:
                raise RuntimeError("AtomSpace socket belongs to another IterBrow workspace")
            _rpc(atomspace_socket, "quiesce")
            checkpoint = _rpc(atomspace_socket, "checkpoint")
            _rpc(atomspace_socket, "shutdown")
            deadline = time.time() + 5
            while time.time() < deadline and atomspace_socket.exists():
                time.sleep(0.1)
    return {"checkpoint": checkpoint, "retired_iter_pid": retired}


def validate_atomspace(root, python_bin, initialize_if_missing=False):
    root = root.resolve()
    # Keep a virtual-environment interpreter path intact.  Resolving this
    # symlink would invoke the base interpreter and lose the installed Hyperon
    # package that the validation is specifically intended to prove.
    python_bin = Path(os.path.abspath(str(python_bin.expanduser())))
    iter_dir = root / "iter"
    state_dir = iter_dir / ".runtime" / "atomspace"
    if not python_bin.is_file() or not os.access(python_bin, os.X_OK):
        raise RuntimeError("AtomSpace validation Python is not executable: %s" % python_bin)
    if not (iter_dir / "metta_server.py").is_file():
        raise RuntimeError("AtomSpace server is missing from the staged installation")
    if not state_dir.is_dir():
        if not initialize_if_missing:
            raise RuntimeError("restored AtomSpace state directory is missing: %s" % state_dir)
        state_dir.mkdir(parents=True, mode=0o700)
    existing_socket = _instance_socket(root, "metta")
    if existing_socket.exists():
        try:
            status = _rpc(existing_socket, "status")
        except Exception:
            status = None
        if status:
            if (
                str(Path(status.get("iter_dir", "")).resolve()) != str(iter_dir)
                or str(Path(status.get("state_dir", "")).resolve()) != str(state_dir)
            ):
                raise RuntimeError("live AtomSpace belongs to another workspace")
            if status.get("ready") is not True or status.get("engine") != "hyperon":
                raise RuntimeError("live AtomSpace is not ready on Hyperon")
            return {"existing": True, "status": status}

    with tempfile.TemporaryDirectory(prefix="iterbrow-state-validate-") as temporary:
        temporary_path = Path(temporary)
        socket_path = temporary_path / "atomspace.sock"
        log_path = temporary_path / "atomspace.log"
        environment = dict(os.environ)
        environment.update({
            "ITER_DIR": str(iter_dir),
            "ITER_METTA_SOCKET": str(socket_path),
            "ITER_METTA_LOCKFILE": str(state_dir / "service.lock"),
            "ITER_ATOMSPACE_STATE_DIR": str(state_dir),
            "ITER_METTA_WORKDIR": str(temporary_path / "work"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        })
        with log_path.open("ab") as log:
            process = subprocess.Popen(
                [str(python_bin), str(iter_dir / "metta_server.py")],
                cwd=str(root), env=environment, stdin=subprocess.DEVNULL,
                stdout=log, stderr=log,
            )
        status = None
        try:
            deadline = time.time() + 25
            while time.time() < deadline:
                if process.poll() is not None:
                    break
                try:
                    status = _rpc(socket_path, "status", timeout=0.5)
                    if status.get("ready") is True:
                        break
                except Exception:
                    pass
                time.sleep(0.1)
            if not status or status.get("ready") is not True or status.get("engine") != "hyperon":
                output = log_path.read_text(encoding="utf-8", errors="replace")[-8000:]
                raise RuntimeError("restored AtomSpace did not validate:\n%s" % output)
            if not isinstance(status.get("commit"), int) or not status.get("state_hash"):
                raise RuntimeError("restored AtomSpace has no durable commit/hash identity")
            if str(Path(status.get("state_dir", "")).resolve()) != str(state_dir):
                raise RuntimeError("validator opened the wrong AtomSpace state directory")
            _rpc(socket_path, "shutdown")
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        return {"existing": False, "status": status}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("snapshot", "restore"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--root", required=True, type=Path)
        sub.add_argument("--archive", required=True, type=Path)
        if command == "snapshot":
            sub.add_argument("--include-tools", action="store_true")
    prepare = subparsers.add_parser("prepare-offline")
    prepare.add_argument("--root", required=True, type=Path)
    validate = subparsers.add_parser("validate-atomspace")
    validate.add_argument("--root", required=True, type=Path)
    validate.add_argument("--python", required=True, type=Path)
    validate.add_argument("--initialize-if-missing", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "snapshot":
        result = snapshot(args.root, args.archive, include_tools=args.include_tools)
    elif args.command == "restore":
        result = restore(args.root, args.archive)
    elif args.command == "prepare-offline":
        result = prepare_offline(args.root)
    else:
        result = validate_atomspace(
            args.root, args.python, initialize_if_missing=args.initialize_if_missing
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
