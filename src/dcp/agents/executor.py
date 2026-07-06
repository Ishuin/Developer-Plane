"""Headless coding-agent executor (propose-only).

Runs a configurable CLI (default: Claude Code `claude -p`) inside a
project directory with an assembled task brief. The agent may modify the
working tree but is instructed never to commit; the executor captures a
before/after git delta so the run can be reviewed and reverted.
"""

import logging
import os
import subprocess
import tempfile
from typing import Dict, List, Tuple

from dcp.config import Settings

logger = logging.getLogger(__name__)


class ExecutionOutcome:
    def __init__(self, exit_code: int, report: str, diff_stat: str,
                 changed_files: List[str]):
        self.exit_code = exit_code
        self.report = report
        self.diff_stat = diff_stat
        self.changed_files = changed_files


class CodeAgentExecutor:
    def __init__(self, settings: Settings):
        self.settings = settings

    def execute(self, project_path: str, brief: str) -> ExecutionOutcome:
        before = _git_state(project_path)

        template = self.settings.agent_cmd
        brief_file: str = ""
        stdin_input: str = ""
        if "{brief_file}" in template:
            # Custom template wants a file: keep it INSIDE the project so
            # sandboxed agents (e.g. Claude Code) are allowed to read it.
            brief_file = os.path.join(project_path, ".dcp_brief.md")
            with open(brief_file, "w", encoding="utf-8") as fh:
                fh.write(brief)
            cmd = template.format(brief_file=brief_file)
        else:
            # Default: pipe the brief via stdin — no shell substitution,
            # no temp files, works identically on Windows and Unix.
            cmd = template
            stdin_input = brief

        try:
            logger.info("Agent run in %s: %s", project_path, cmd)
            try:
                res = subprocess.run(
                    cmd, shell=True, cwd=project_path,
                    capture_output=True, text=True,
                    input=stdin_input if stdin_input else None,
                    timeout=self.settings.agent_timeout,
                )
                exit_code = res.returncode
                report = (res.stdout or "")[-8000:]
                if res.returncode != 0 and res.stderr:
                    report += "\n--- stderr ---\n" + res.stderr[-2000:]
            except subprocess.TimeoutExpired:
                exit_code, report = -1, f"timed out after {self.settings.agent_timeout}s"
        finally:
            if brief_file:
                try:
                    os.unlink(brief_file)
                except OSError:
                    pass

        after = _git_state(project_path)
        changed = sorted(set(after) - set(before))
        diff_stat = _diff_stat(project_path, changed)
        return ExecutionOutcome(exit_code, report, diff_stat, changed)


# Tooling artifacts that must never count as agent-proposed changes.
_IGNORED_CHANGE_PREFIXES = (".omc", ".claude", ".dcp_brief", "AGENT_NOTES.md")


def _git_state(path: str) -> Dict[str, str]:
    """Map of dirty-file path -> status code ('' if not a git repo)."""
    if not os.path.isdir(os.path.join(path, ".git")):
        return {}
    try:
        res = subprocess.run(
            ["git", "-C", path, "status", "--porcelain"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        state = {}
        for line in res.stdout.splitlines():
            if len(line) <= 3:
                continue
            rel = line[3:].strip().strip('"')
            norm = rel.replace("\\", "/")
            if norm.startswith("./"):
                norm = norm[2:]
            if norm.startswith(_IGNORED_CHANGE_PREFIXES):
                continue
            state[rel] = line[:2]
        return state
    except (OSError, subprocess.TimeoutExpired):
        return {}


def _diff_stat(path: str, changed_files: List[str]) -> str:
    if not changed_files:
        return ""
    try:
        res = subprocess.run(
            ["git", "-C", path, "diff", "--stat", "--", *changed_files[:100]],
            capture_output=True, text=True, timeout=15, check=False,
        )
        stat = res.stdout.strip()
        untracked = [f for f in changed_files if _is_untracked(path, f)]
        if untracked:
            stat += "\nnew files: " + ", ".join(untracked[:20])
        return stat or "changes: " + ", ".join(changed_files[:20])
    except (OSError, subprocess.TimeoutExpired):
        return "changes: " + ", ".join(changed_files[:20])


def _is_untracked(path: str, rel: str) -> bool:
    res = subprocess.run(
        ["git", "-C", path, "ls-files", "--error-unmatch", rel],
        capture_output=True, timeout=10, check=False,
    )
    return res.returncode != 0


def revert_changed_files(path: str, changed_files: List[str]) -> Tuple[bool, str]:
    """Restore tracked files, delete untracked ones a run introduced."""
    if not os.path.isdir(os.path.join(path, ".git")):
        return False, "not a git repository — cannot safely revert"
    errors = []
    for rel in changed_files:
        full = os.path.join(path, rel)
        try:
            if _is_untracked(path, rel):
                if os.path.isfile(full):
                    os.unlink(full)
            else:
                subprocess.run(
                    ["git", "-C", path, "checkout", "--", rel],
                    capture_output=True, timeout=15, check=True,
                )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            errors.append(f"{rel}: {exc}")
    return (not errors), "; ".join(errors)
