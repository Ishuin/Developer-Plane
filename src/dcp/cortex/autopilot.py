"""Autopilot: run coding agents over the completion-priority queue.

Propose-only: every run leaves changes uncommitted plus an agent_runs
record with a diff summary. The user approves (keeps changes) or
discards (reverts the exact files the run touched) from the UI.
"""

import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from dcp.agents.executor import CodeAgentExecutor, revert_changed_files
from dcp.core.models import AgentRun
from dcp.cortex.completion import CompletionEngine, CompletionResult
from dcp.cortex.context import ContextAssembler
from dcp.cortex.inference import StageInferenceEngine
from dcp.database import EventSourcingDB
from dcp.sentry.genome import build_genome

logger = logging.getLogger(__name__)

HARD_RULES = """
## Rules (non-negotiable)
- Work ONLY inside this project directory.
- Do NOT run git commit, git push, or modify anything under .git.
- Do NOT touch files outside this directory.
- Focus on the listed tasks; stop when they are done.
- If a task is impossible, note why in a file named AGENT_NOTES.md and move on.
"""


def build_task_brief(
    context: Dict[str, Any],
    completion: Optional[CompletionResult] = None,
    next_steps: Optional[List[str]] = None,
) -> str:
    parts = [ContextAssembler.to_prompt(context)]
    if completion and completion.failed:
        parts.append("\n## Definition-of-Done gaps (close these)")
        parts += [f"- {name}" for name in completion.failed]
    if next_steps:
        parts.append("\n## Tasks (priority order)")
        parts += [f"{i + 1}. {step}" for i, step in enumerate(next_steps)]
    parts.append(HARD_RULES)
    return "\n".join(parts)


class AutopilotInProgress(RuntimeError):
    pass


class AutopilotManager:
    def __init__(
        self,
        db: EventSourcingDB,
        executor: CodeAgentExecutor,
        completion: CompletionEngine,
        inference: StageInferenceEngine,
        assembler: ContextAssembler,
    ):
        self.db = db
        self.executor = executor
        self.completion = completion
        self.inference = inference
        self.assembler = assembler
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._status: Dict[str, Any] = {
            "running": False, "total": 0, "done": 0, "skipped": 0, "failed": 0,
            "current": None, "started_at": None, "finished_at": None,
            "log": [],
        }

    # --------------------------------------------------------------- control
    def start(
        self, limit: int = 3, paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if paths:
            queue = [p for p in (self.db.get_project(x) for x in paths) if p]
        else:
            queue = self.db.autopilot_queue(limit=limit)
        with self._lock:
            if self._status["running"]:
                raise AutopilotInProgress("autopilot batch already running")
            self._status = {
                "running": True, "total": len(queue), "done": 0, "skipped": 0,
                "failed": 0, "current": None,
                "started_at": datetime.now().isoformat(),
                "finished_at": None, "log": [],
            }
            self._thread = threading.Thread(
                target=self._run_batch, args=([p.path for p in queue],),
                daemon=True,
            )
            self._thread.start()
        return self.status()

    def status(self) -> Dict[str, Any]:
        with self._lock:
            snapshot = dict(self._status)
            snapshot["log"] = list(snapshot["log"])
            return snapshot

    def wait(self, timeout: Optional[float] = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    # ----------------------------------------------------------------- batch
    def _run_batch(self, paths: List[str]) -> None:
        try:
            for path in paths:  # sequential: agent runs are heavy
                with self._lock:
                    self._status["current"] = path
                try:
                    outcome = self.run_project(path)
                    with self._lock:
                        self._status[outcome] += 1
                        self._status["log"].append(f"{outcome}: {path}")
                except Exception as exc:  # noqa: BLE001 - isolate per project
                    logger.exception("Autopilot failed on %s", path)
                    with self._lock:
                        self._status["failed"] += 1
                        self._status["log"].append(f"failed: {path} ({exc})")
        finally:
            with self._lock:
                self._status["running"] = False
                self._status["current"] = None
                self._status["finished_at"] = datetime.now().isoformat()

    # --------------------------------------------------------------- one run
    def run_project(self, path: str) -> str:
        """Returns 'done' or 'skipped' (guards); raises on hard failure."""
        if not os.path.isdir(path):
            raise FileNotFoundError(f"directory gone: {path}")

        genome = build_genome(path)
        # Guard 1: never touch a repo with pre-existing uncommitted work.
        if genome.git.get("is_repo") and genome.git.get("dirty_files", 0) > 0:
            logger.info("Skip %s: dirty working tree", path)
            return "skipped"
        # Guard 2: one pending proposal per project.
        if self.db.get_agent_runs(limit=1, project_id=path, pending_only=True):
            logger.info("Skip %s: pending run awaiting verdict", path)
            return "skipped"

        completion = self.completion.evaluate(path, genome=genome)
        stage = self.inference.infer_stage(path, genome=genome)
        context = self.assembler.assemble(path, genome=genome, stage=stage)
        next_steps = self._latest_next_steps(path)
        brief = build_task_brief(context, completion=completion, next_steps=next_steps)

        run = self.db.insert_agent_run(AgentRun(project_id=path, task_brief=brief))
        outcome = self.executor.execute(path, brief)
        self.db.finish_agent_run(
            run.id, outcome.exit_code, outcome.diff_stat, outcome.report
        )
        self.db.log_decision(
            "AgentRunProposed",
            {"run_id": run.id, "exit_code": outcome.exit_code,
             "changed_files": outcome.changed_files[:50]},
            project_id=path,
        )
        return "done"

    def _latest_next_steps(self, path: str) -> List[str]:
        """Recommendations from the latest status analysis, if any."""
        for inference in self.db.get_inferences(limit=10, project_id=path):
            if inference.inference_type == "ProjectStatusReport":
                # Re-read the report file for next steps (headline lives in data).
                report_path = os.path.join(path, "project_status.md")
                if os.path.isfile(report_path):
                    return _extract_next_steps(report_path)
                break
        return []

    # --------------------------------------------------------------- verdict
    def apply_verdict(self, run_id: int, verdict: str) -> Dict[str, Any]:
        run = self.db.get_agent_run(run_id)
        if run is None:
            raise KeyError(f"no such run: {run_id}")
        if run.verdict:
            raise ValueError(f"run {run_id} already {run.verdict}")
        if run.finished_at is None:
            raise ValueError(f"run {run_id} still executing")

        result: Dict[str, Any] = {"run_id": run_id, "verdict": verdict}
        if verdict == "discarded":
            changed = _changed_files_from_decision(self.db, run_id)
            ok, errors = revert_changed_files(run.project_id, changed)
            result["reverted"] = ok
            if errors:
                result["errors"] = errors
        self.db.set_run_verdict(run_id, verdict)
        self.db.log_decision(
            "AgentRunVerdict", {"run_id": run_id, "verdict": verdict},
            project_id=run.project_id,
        )
        return result


def _extract_next_steps(report_path: str) -> List[str]:
    steps, in_section = [], False
    try:
        with open(report_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("## Suggested next steps"):
                    in_section = True
                elif line.startswith("## "):
                    in_section = False
                elif in_section and line.strip().startswith("- "):
                    steps.append(line.strip()[2:])
    except OSError:
        pass
    return steps[:5]


def _changed_files_from_decision(db: EventSourcingDB, run_id: int) -> List[str]:
    for decision in db.get_decisions(limit=500):
        if (decision.decision_type == "AgentRunProposed"
                and decision.data.get("run_id") == run_id):
            return decision.data.get("changed_files", [])
    return []
