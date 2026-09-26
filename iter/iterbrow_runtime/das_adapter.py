"""DAS projection boundary.

DAS consumes committed canonical events and owns only its projection cursor.
The default adapter is disabled. A file adapter exercises the same contract in
tests and local development without pretending that a live DAS write API exists.
"""

import json
import os
import threading
import time
from pathlib import Path


class DASAdapter:
    name = "abstract"

    def apply(self, event):
        raise NotImplementedError

    def close(self):
        return None


class DisabledDASAdapter(DASAdapter):
    name = "disabled"

    def apply(self, event):
        return None


class FileDASAdapter(DASAdapter):
    """Deterministic local contract adapter used for integration testing."""

    name = "file"

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def apply(self, event):
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def adapter_from_environment(runtime_dir):
    mode = os.environ.get("ITER_DAS_ADAPTER", "disabled").strip().lower()
    if mode in ("", "disabled", "off", "none"):
        return DisabledDASAdapter()
    if mode == "file":
        path = os.environ.get(
            "ITER_DAS_FILE", str(Path(runtime_dir) / "das_projection" / "events.jsonl")
        )
        return FileDASAdapter(path)
    raise RuntimeError(
        "Unsupported ITER_DAS_ADAPTER=%s. Live DAS remains intentionally "
        "unimplemented until it satisfies the canonical adapter contract." % mode
    )


class DASProjectionWorker:
    def __init__(self, fetch_events, runtime_dir, poll_interval=1.0, current_epoch=None):
        self.fetch_events = fetch_events
        self.runtime_dir = Path(runtime_dir)
        self.cursor_path = self.runtime_dir / "das_projection" / "cursor.json"
        self.adapter = adapter_from_environment(runtime_dir)
        self.poll_interval = float(poll_interval)
        self.current_epoch = current_epoch
        self.stop_event = threading.Event()
        self.thread = None
        self.last_error = None
        self.cursor = self._load_cursor()

    def _load_cursor(self):
        try:
            return json.loads(self.cursor_path.read_text(encoding="utf-8"))
        except Exception:
            return {"epoch": None, "commit": 0}

    def _save_cursor(self):
        self.cursor_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cursor_path.with_name(self.cursor_path.name + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(self.cursor, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(self.cursor_path))

    def run_once(self):
        epoch = self.current_epoch() if self.current_epoch else None
        if epoch and self.cursor.get("epoch") not in (None, epoch):
            self.cursor = {"epoch": epoch, "commit": 0}
        batch = self.fetch_events(self.cursor.get("commit", 0), 100)
        for event in batch:
            if self.cursor.get("epoch") not in (None, event["epoch"]):
                self.cursor = {"epoch": event["epoch"], "commit": 0}
            self.adapter.apply(event)
            self.cursor = {"epoch": event["epoch"], "commit": event["commit"]}
            self._save_cursor()
        self.last_error = None
        return len(batch)

    def _run(self):
        while not self.stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                self.last_error = "%s: %s" % (type(exc).__name__, exc)
            self.stop_event.wait(self.poll_interval)

    def start(self):
        if self.adapter.name == "disabled" or self.thread:
            return
        self.thread = threading.Thread(target=self._run, name="das-projection", daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        self.adapter.close()

    def status(self):
        return {
            "adapter": self.adapter.name,
            "authoritative": False,
            "cursor": dict(self.cursor),
            "last_error": self.last_error,
            "running": bool(self.thread and self.thread.is_alive()),
        }
