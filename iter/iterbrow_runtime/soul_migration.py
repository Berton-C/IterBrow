"""Archive the files the retired keyword Soul kept (docs/milestones/M6_soul_base.md D).

Runs once on AtomSpace service start (where the kb backfill runs). Moves the legacy
state files into backups/soul-legacy-<timestamp>/ so nothing is lost and nothing reads
them again. Idempotent: when none are present it does nothing.
"""
import shutil
import time
from pathlib import Path

LEGACY_STATE = ("memory/soul_state.json", "memory/soul_gate_log.json",
                "memory/soul_calibration.json", "memory/soul_skills.json")


def archive_legacy_soul_files(iter_dir):
    """Returns the archive directory, or None when there was nothing to archive."""
    root = Path(iter_dir)
    present = [root / rel for rel in LEGACY_STATE if (root / rel).is_file()]
    if not present:
        return None
    archive = root / "backups" / ("soul-legacy-%s" % time.strftime("%Y%m%d-%H%M%S"))
    suffix = 0
    while archive.exists():
        suffix += 1
        archive = archive.with_name(archive.name.split(".")[0] + ".%d" % suffix)
    archive.mkdir(parents=True)
    for path in present:
        shutil.move(str(path), str(archive / path.name))
    return archive
