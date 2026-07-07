"""Git operations for WIP triage: diff, test, branch-commit, push, PR URL.

Turns "uncommitted changes — go fix it in your editor" into dashboard
actions: review the diff, run the project's own tests, commit everything
to a dcp/ branch, push it, and open the PR compare page.
"""

import logging
import os
import re
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DIFF_CAP = 200_000  # chars
_TEST_TIMEOUT = 600


def _git(path: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", path, *args],
        capture_output=True, text=True, timeout=timeout, check=False,
    )


def is_repo(path: str) -> bool:
    return os.path.isdir(os.path.join(path, ".git"))


def dirty_files(path: str) -> List[Dict[str, str]]:
    res = _git(path, "status", "--porcelain")
    files = []
    for line in res.stdout.splitlines():
        if len(line) > 3:
            files.append({"status": line[:2].strip() or "??",
                          "path": line[3:].strip().strip('"')})
    return files


def diff_text(path: str) -> str:
    """Diff of tracked changes plus names of untracked files, size-capped."""
    tracked = _git(path, "diff", "HEAD", timeout=60).stdout
    untracked = [f["path"] for f in dirty_files(path) if f["status"] == "??"]
    parts = [tracked]
    if untracked:
        parts.append("\n# Untracked files (full content not shown):\n"
                     + "\n".join(f"+ {u}" for u in untracked))
    text = "\n".join(p for p in parts if p)
    return text[:_DIFF_CAP] + ("\n… (diff truncated)" if len(text) > _DIFF_CAP else "")


def current_branch(path: str) -> str:
    return _git(path, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def remote_url(path: str) -> Optional[str]:
    res = _git(path, "remote", "get-url", "origin")
    return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else None


def github_repo_slug(path: str) -> Optional[str]:
    """'owner/repo' when origin points at GitHub, else None."""
    url = remote_url(path)
    if not url or "github.com" not in url:
        return None
    match = re.search(r"github\.com[/:]([^/]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return f"{match.group(1)}/{match.group(2)}" if match else None


# ------------------------------------------------------------------ testing
def detect_test_command(path: str) -> Optional[str]:
    """The project's own test entry point, best effort."""
    from dcp.cortex.completion import load_dod

    for assertion in load_dod(path):
        if assertion.type == "command" and assertion.run and \
                "test" in assertion.name.lower():
            return assertion.run
    entries = set(os.listdir(path)) if os.path.isdir(path) else set()
    if {"pytest.ini", "setup.cfg", "pyproject.toml"} & entries or "tests" in entries:
        if any(e.endswith(".py") for e in entries) or "tests" in entries:
            return "python -m pytest -q --maxfail=5"
    if "package.json" in entries:
        try:
            import json
            with open(os.path.join(path, "package.json"), encoding="utf-8") as fh:
                if "test" in (json.load(fh).get("scripts") or {}):
                    return "npm test --silent"
        except (OSError, ValueError):
            pass
    if "Cargo.toml" in entries:
        return "cargo test --quiet"
    if "go.mod" in entries:
        return "go test ./..."
    return None


def run_tests(path: str, command: Optional[str] = None) -> Dict[str, Any]:
    command = command or detect_test_command(path)
    if not command:
        return {"ran": False, "reason": "no test command detected "
                                        "(add a dod.yaml 'tests' assertion)"}
    try:
        res = subprocess.run(
            command, shell=True, cwd=path, capture_output=True, text=True,
            timeout=_TEST_TIMEOUT,
        )
        output = ((res.stdout or "") + ("\n" + res.stderr if res.stderr else ""))
        return {"ran": True, "command": command, "exit_code": res.returncode,
                "passed": res.returncode == 0, "output": output[-10_000:]}
    except subprocess.TimeoutExpired:
        return {"ran": True, "command": command, "exit_code": -1,
                "passed": False, "output": f"timed out after {_TEST_TIMEOUT}s"}


# ----------------------------------------------------------- commit + PR
def commit_wip_to_branch(
    path: str, message: str, branch: Optional[str] = None,
) -> Tuple[str, str]:
    """Commit ALL uncommitted work to a new branch; return (branch, sha).

    Stays on the new branch afterwards: the working tree ends clean, the
    WIP lives safely in a commit, and the PR flow can push it directly.
    """
    if not is_repo(path):
        raise RuntimeError("not a git repository")
    if not dirty_files(path):
        raise RuntimeError("nothing to commit — working tree is clean")

    branch = branch or f"dcp/wip-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    checkout = _git(path, "checkout", "-b", branch)
    if checkout.returncode != 0:
        raise RuntimeError(f"branch creation failed: {checkout.stderr.strip()}")
    _git(path, "add", "-A")
    commit = _git(path, "commit", "-m", message or "WIP triage via Developer Control Plane")
    if commit.returncode != 0:
        raise RuntimeError(f"commit failed: {commit.stderr.strip() or commit.stdout.strip()}")
    sha = _git(path, "rev-parse", "--short", "HEAD").stdout.strip()
    return branch, sha


def push_branch(path: str, branch: str) -> Dict[str, Any]:
    if remote_url(path) is None:
        return {"pushed": False, "reason": "no remote configured"}
    res = _git(path, "push", "-u", "origin", branch, timeout=120)
    if res.returncode != 0:
        return {"pushed": False, "reason": (res.stderr or res.stdout).strip()[-500:]}
    result: Dict[str, Any] = {"pushed": True}
    slug = github_repo_slug(path)
    if slug:
        result["pr_url"] = f"https://github.com/{slug}/compare/{branch}?expand=1"
    return result


def discard_all_wip(path: str) -> Dict[str, Any]:
    """Revert every uncommitted change (tracked reset + untracked removal)."""
    if not is_repo(path):
        raise RuntimeError("not a git repository")
    count = len(dirty_files(path))
    _git(path, "checkout", "--", ".")
    clean = _git(path, "clean", "-fd")
    if clean.returncode != 0:
        raise RuntimeError(f"clean failed: {clean.stderr.strip()}")
    return {"discarded": count}
