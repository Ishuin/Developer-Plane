"""Background scan jobs: run discovery in a thread, expose live progress."""

import threading
from datetime import datetime
from typing import Any, Dict, Optional

from dcp.sentry.discovery import ProjectDiscovery


class ScanInProgress(RuntimeError):
    """Raised when a scan is requested while another is still running."""


class ScanManager:
    """Owns at most one running discovery scan and its status snapshot."""

    def __init__(self, discovery: ProjectDiscovery):
        self.discovery = discovery
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._status: Dict[str, Any] = {
            "running": False,
            "root": None,
            "found": 0,
            "started_at": None,
            "finished_at": None,
            "error": None,
        }

    def start(self, root: str) -> Dict[str, Any]:
        with self._lock:
            if self._status["running"]:
                raise ScanInProgress(f"scan of {self._status['root']} still running")
            self._status = {
                "running": True,
                "root": root,
                "found": 0,
                "started_at": datetime.now().isoformat(),
                "finished_at": None,
                "error": None,
            }
            self._thread = threading.Thread(
                target=self._run, args=(root,), daemon=True
            )
            self._thread.start()
        return self.status()

    def _run(self, root: str) -> None:
        try:
            self.discovery.scan(root, on_found=self._on_found)
        except Exception as exc:  # noqa: BLE001 - surface any failure in status
            with self._lock:
                self._status["error"] = str(exc)
        finally:
            with self._lock:
                self._status["running"] = False
                self._status["finished_at"] = datetime.now().isoformat()

    def _on_found(self, _project) -> None:
        with self._lock:
            self._status["found"] += 1

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def wait(self, timeout: Optional[float] = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
