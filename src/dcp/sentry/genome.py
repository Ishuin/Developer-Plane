"""Project Genome: the detected identity of a project.

Cheap, deterministic, offline — one directory listing plus optional git
metadata read directly from .git (no subprocess unless git exists).
"""

import os
import subprocess
from typing import Any, Dict

from dcp.core.models import Genome
from dcp.sentry.detectors import STRONG_INDICATORS, detect

TEST_HINTS = ("tests", "test", "__tests__", "spec", "specs")
DOC_HINTS = ("docs", "doc", "README.md", "README.rst", "README.txt")
CI_HINTS = (".github", ".gitlab-ci.yml", ".circleci", "azure-pipelines.yml", "Jenkinsfile")


def build_genome(path: str) -> Genome:
    try:
        entries = os.listdir(path)
    except OSError:
        return Genome(path=path)

    entry_set = set(entries)
    genome = Genome(
        path=path,
        type=detect(entries),
        markers=sorted(entry_set & STRONG_INDICATORS),
        has_tests=any(h in entry_set for h in TEST_HINTS),
        has_docs=any(h in entry_set for h in DOC_HINTS),
        has_ci=any(h in entry_set for h in CI_HINTS),
        has_dockerfile="Dockerfile" in entry_set or "docker-compose.yml" in entry_set,
    )
    if ".git" in entry_set:
        genome.git = _git_info(path)
    return genome


def _git_info(path: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {"is_repo": True}
    try:
        head = subprocess.run(
            ["git", "-C", path, "log", "-1", "--format=%H|%cI|%s"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if head.returncode == 0 and head.stdout.strip():
            sha, date, subject = head.stdout.strip().split("|", 2)
            info.update({"last_commit": sha[:12], "last_commit_date": date,
                         "last_commit_subject": subject})
        branch = subprocess.run(
            ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if branch.returncode == 0:
            info["branch"] = branch.stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", path, "status", "--porcelain"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if dirty.returncode == 0:
            info["dirty_files"] = len([l for l in dirty.stdout.splitlines() if l.strip()])
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return info
