"""Parallel project status analysis.

AnalysisManager fans a StatusReportAgent out over many projects with a
bounded worker pool, writes project_status.md into each project, updates
the projects projection, and exposes live batch progress — same shape as
sentry.scanner.ScanManager.
"""

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

from dcp.agents.status_agent import ProjectStatus, StatusReportAgent
from dcp.cortex.context import ContextAssembler
from dcp.cortex.inference import StageInferenceEngine
from dcp.database import EventSourcingDB

logger = logging.getLogger(__name__)

STATUS_FILENAME = "project_status.md"


class AnalysisInProgress(RuntimeError):
    """Raised when a batch is requested while another is still running."""


class AnalysisManager:
    def __init__(
        self,
        db: EventSourcingDB,
        agent: StatusReportAgent,
        inference: StageInferenceEngine,
        assembler: ContextAssembler,
        max_workers: int = 4,
    ):
        self.db = db
        self.agent = agent
        self.inference = inference
        self.assembler = assembler
        self.max_workers = max(1, max_workers)
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._status: Dict[str, Any] = {
            "running": False, "total": 0, "done": 0, "failed": 0,
            "current": [], "started_at": None, "finished_at": None,
            "errors": {},
        }

    # ------------------------------------------------------------- batch API
    def start(self, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        if not paths:
            items, _ = self.db.list_projects(limit=100000, offset=0)
            paths = [p.path for p in items]
        with self._lock:
            if self._status["running"]:
                raise AnalysisInProgress("analysis batch already running")
            self._status = {
                "running": True, "total": len(paths), "done": 0, "failed": 0,
                "current": [], "started_at": datetime.now().isoformat(),
                "finished_at": None, "errors": {},
            }
            self._thread = threading.Thread(
                target=self._run_batch, args=(list(paths),), daemon=True
            )
            self._thread.start()
        return self.status()

    def status(self) -> Dict[str, Any]:
        with self._lock:
            snapshot = dict(self._status)
            snapshot["current"] = list(snapshot["current"])
            snapshot["errors"] = dict(snapshot["errors"])
            return snapshot

    def wait(self, timeout: Optional[float] = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    # ----------------------------------------------------------- single item
    def analyze_one(self, path: str) -> ProjectStatus:
        """Analyze a single project synchronously (also used by the batch)."""
        stage = self.inference.infer_stage(path)
        context = self.assembler.assemble(path, stage=stage)
        status = self.agent.build_status(context)

        report_path = os.path.join(path, STATUS_FILENAME)
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write(status.to_markdown())

        self.db.set_project_status(path, status.headline, status.health)
        self.db.log_inference(
            "ProjectStatusReport",
            {"headline": status.headline, "health": status.health,
             "tier": status.tier},
            confidence_score=0.9 if status.tier == 1 else 0.6,
            project_id=path,
        )
        self.db.log_decision(
            "StatusFileWritten",
            {"file": report_path, "tier": status.tier},
            project_id=path,
        )
        return status

    # ---------------------------------------------------------------- worker
    def _run_batch(self, paths: List[str]) -> None:
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = {
                    pool.submit(self._safe_analyze, p): p for p in paths
                }
                for future in as_completed(futures):
                    future.result()  # _safe_analyze never raises
        finally:
            with self._lock:
                self._status["running"] = False
                self._status["finished_at"] = datetime.now().isoformat()
                self._status["current"] = []

    def _safe_analyze(self, path: str) -> None:
        with self._lock:
            self._status["current"].append(path)
        try:
            if not os.path.isdir(path):
                raise FileNotFoundError(f"directory gone: {path}")
            self.analyze_one(path)
            with self._lock:
                self._status["done"] += 1
        except Exception as exc:  # noqa: BLE001 - one failure must not kill batch
            logger.warning("Analysis failed for %s: %s", path, exc)
            with self._lock:
                self._status["failed"] += 1
                self._status["errors"][path] = str(exc)
        finally:
            with self._lock:
                if path in self._status["current"]:
                    self._status["current"].remove(path)
