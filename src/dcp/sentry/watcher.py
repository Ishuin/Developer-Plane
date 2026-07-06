"""Filesystem watcher: OS-level hooks via watchdog, zero polling."""

import logging
import os
from typing import Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from dcp.core.bus import EventBus, bus as default_bus
from dcp.database import EventSourcingDB

logger = logging.getLogger(__name__)

# Noise we never want in the event log.
IGNORED_PARTS = (".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache")
IGNORED_SUFFIXES = (".db", ".db-journal", ".db-wal", ".db-shm", ".pyc", ".tmp")


class SentryWatcher(FileSystemEventHandler):
    """Emits FileChanged/FileCreated/FileDeleted/FileMoved signals."""

    def __init__(self, db: EventSourcingDB, event_bus: Optional[EventBus] = None):
        super().__init__()
        self.db = db
        self.bus = event_bus or default_bus
        self._observer: Optional[Observer] = None

    # ------------------------------------------------------------- lifecycle
    def start(self, path: str = ".") -> None:
        if self._observer is not None:
            logger.warning("Watcher already running")
            return
        self._observer = Observer()
        self._observer.schedule(self, path, recursive=True)
        self._observer.start()
        logger.info("Sentry watching %s", os.path.abspath(path))

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
        return norm.endswith(IGNORED_SUFFIXES)

    def _emit(self, event_type: str, event: FileSystemEvent, **extra) -> None:
        if self._should_ignore(event.src_path):
            return
        payload = {
            "src_path": event.src_path,
            "is_directory": event.is_directory,
            **extra,
        }
        self.db.log_signal(event_type, payload)
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
