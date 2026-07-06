"""Filesystem watcher: OS-level hooks via watchdog, zero polling."""

import logging
import os
import threading
from typing import Iterable, List, Optional, Union

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from dcp.core.bus import EventBus, bus as default_bus
from dcp.database import EventSourcingDB

logger = logging.getLogger(__name__)

# Noise we never want in the event log.
IGNORED_PARTS = (".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache")
IGNORED_SUFFIXES = (".db", ".db-journal", ".db-wal", ".db-shm", ".pyc", ".tmp", ".lock")


class SentryWatcher(FileSystemEventHandler):
    """Emits FileChanged/FileCreated/FileDeleted/FileMoved signals."""

    def __init__(self, db: EventSourcingDB, event_bus: Optional[EventBus] = None):
        super().__init__()
        self.db = db
        self.bus = event_bus or default_bus
        self._observer: Optional[Observer] = None
        # Registered project roots, longest first, for event attribution.
        self._roots: List[str] = []
        self._roots_lock = threading.Lock()
        self.bus.subscribe("ProjectDiscovered", self._on_project_discovered)

    def refresh_roots(self) -> None:
        """Reload registered project paths used to attribute file events."""
        items, _ = self.db.list_projects(limit=100000, offset=0)
        with self._roots_lock:
            self._roots = sorted((p.path for p in items), key=len, reverse=True)

    def _on_project_discovered(self, _event_type: str, payload: dict) -> None:
        path = payload.get("path")
        if not path:
            return
        with self._roots_lock:
            if path not in self._roots:
                self._roots.append(path)
                self._roots.sort(key=len, reverse=True)

    def _owning_project(self, src_path: str) -> Optional[str]:
        with self._roots_lock:
            for root in self._roots:
                if src_path == root or src_path.startswith(root + os.sep):
                    return root
        return None

    # ------------------------------------------------------------- lifecycle
    def start(self, paths: Union[str, Iterable[str]] = ".") -> None:
        if self._observer is not None:
            logger.warning("Watcher already running")
            return
        if isinstance(paths, str):
            paths = [paths]
        self.refresh_roots()
        self._observer = Observer()
        for path in paths:
            self._observer.schedule(self, path, recursive=True)
            logger.info("Sentry watching %s", os.path.abspath(path))
        self._observer.start()

    def stop(self) -> None:
        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join()
        self._observer = None
        logger.info("Sentry stopped")

    @property
    def is_running(self) -> bool:
        return self._observer is not None

    # ---------------------------------------------------------------- events
    def _should_ignore(self, path: str) -> bool:
        norm = path.replace("\\", "/")
        if any(f"/{part}/" in norm or norm.endswith(f"/{part}") for part in IGNORED_PARTS):
            return True
        # Any dot-directory segment (".omc/", ".idea/", …) is noise; a leading
        # dot on the final segment (".gitignore") is still a real file edit.
        if any(seg.startswith(".") for seg in norm.split("/")[:-1] if seg):
            return True
        return norm.endswith(IGNORED_SUFFIXES)

    def _emit(self, event_type: str, event: FileSystemEvent, **extra) -> None:
        if self._should_ignore(event.src_path):
            return
        project_id = self._owning_project(event.src_path)
        payload = {
            "src_path": event.src_path,
            "is_directory": event.is_directory,
            **extra,
        }
        self.db.log_signal(event_type, payload, project_id=project_id)
        if project_id:
            self.db.touch_project(project_id)
        self.bus.publish(event_type, payload)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._emit("FileChanged", event)

    def on_created(self, event: FileSystemEvent) -> None:
        self._emit("FileCreated", event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._emit("FileDeleted", event)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._emit("FileMoved", event, dest_path=event.dest_path)
