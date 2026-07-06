"""Completion scoring: code-driven Definition of Done.

A project's completion percent comes from its own dod.yaml when present
(explicit, testable assertions — the PRD's "Code-Driven Definition of
Done"), otherwise from a deterministic genome heuristic.
"""

import logging
import os
import re
import subprocess
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from dcp.core.models import Genome
from dcp.database import EventSourcingDB
from dcp.sentry.genome import build_genome

logger = logging.getLogger(__name__)

DOD_FILENAME = "dod.yaml"
_COMMAND_TIMEOUT = 120
_TODO_PATTERN = re.compile(r"\b(TODO|FIXME|XXX)\b")
_SOURCE_EXTS = (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
                ".rb", ".php", ".c", ".cc", ".cpp", ".h", ".cs")


class Assertion(BaseModel):
    name: str
    type: str  # command | file_exists | max_todos
    run: Optional[str] = None
    path: Optional[str] = None
    limit: int = 0


class CompletionResult(BaseModel):
    project: str
    percent: float = Field(ge=0.0, le=100.0)
    source: str = "heuristic"  # dod | heuristic
    passed: List[str] = Field(default_factory=list)
    failed: List[str] = Field(default_factory=list)


def load_dod(path: str) -> List[Assertion]:
    dod_path = os.path.join(path, DOD_FILENAME)
    if not os.path.isfile(dod_path):
        return []
    try:
        with open(dod_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return [Assertion(**a) for a in data.get("assertions", [])]
    except Exception as exc:  # noqa: BLE001 - malformed DoD falls back to heuristic
        logger.warning("Bad %s in %s: %s", DOD_FILENAME, path, exc)
        return []


class CompletionEngine:
    def __init__(self, db: EventSourcingDB):
        self.db = db

    def evaluate(self, path: str, genome: Optional[Genome] = None) -> CompletionResult:
        assertions = load_dod(path)
        if assertions:
            result = self._evaluate_dod(path, assertions)
        else:
            result = self._evaluate_heuristic(path, genome or build_genome(path))

        self.db.set_project_completion(path, result.percent, result.source)
        self.db.log_inference(
            "CompletionEvaluated",
            {"percent": result.percent, "source": result.source,
             "failed": result.failed},
            confidence_score=1.0 if result.source == "dod" else 0.5,
            project_id=path,
        )
        return result

    # -------------------------------------------------------------- dod path
    def _evaluate_dod(self, path: str, assertions: List[Assertion]) -> CompletionResult:
        passed, failed = [], []
        for assertion in assertions:
            ok = self._check(path, assertion)
            (passed if ok else failed).append(assertion.name)
        percent = round(100.0 * len(passed) / max(1, len(assertions)), 1)
        return CompletionResult(
            project=path, percent=percent, source="dod",
            passed=passed, failed=failed,
        )

    @staticmethod
    def _check(path: str, assertion: Assertion) -> bool:
        try:
            if assertion.type == "command" and assertion.run:
                res = subprocess.run(
                    assertion.run, shell=True, cwd=path,
                    capture_output=True, timeout=_COMMAND_TIMEOUT,
                )
                return res.returncode == 0
            if assertion.type == "file_exists" and assertion.path:
                return os.path.exists(os.path.join(path, assertion.path))
            if assertion.type == "max_todos":
                return _count_todos(path) <= assertion.limit
        except (OSError, subprocess.TimeoutExpired):
            return False
        logger.warning("Unknown assertion type %r in %s", assertion.type, path)
        return False

    # -------------------------------------------------------- heuristic path
    @staticmethod
    def _evaluate_heuristic(path: str, genome: Genome) -> CompletionResult:
        checks = [
            ("version control", 20, bool(genome.git.get("is_repo"))),
            ("tests present", 25, genome.has_tests),
            ("CI configured", 20, genome.has_ci),
            ("docs present", 15, genome.has_docs),
            ("deploy artifacts", 10, genome.has_dockerfile),
            ("clean working tree", 10,
             genome.git.get("is_repo", False) and genome.git.get("dirty_files", 0) == 0),
        ]
        passed = [name for name, _, ok in checks if ok]
        failed = [name for name, _, ok in checks if not ok]
        percent = float(sum(weight for _, weight, ok in checks if ok))
        return CompletionResult(
            project=path, percent=percent, source="heuristic",
            passed=passed, failed=failed,
        )


def _count_todos(path: str, max_files: int = 400) -> int:
    count, seen = 0, 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")
                   and d not in ("node_modules", "__pycache__", "venv", "dist", "build")]
        for name in files:
            if not name.endswith(_SOURCE_EXTS):
                continue
            seen += 1
            if seen > max_files:
                return count
            try:
                with open(os.path.join(root, name), "r",
                          encoding="utf-8", errors="ignore") as fh:
                    count += len(_TODO_PATTERN.findall(fh.read()))
            except OSError:
                continue
    return count
