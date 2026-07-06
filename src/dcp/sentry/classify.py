"""Project kind classification.

Distinguishes the user's own projects from third-party code so agents
never modify libraries:

- ``github``    — git remote owned by one of the user's accounts
- ``library``   — git remote owned by someone else (clones, vendored code)
- ``local-git`` — git repository with no remote (private local work)
- ``local``     — no version control
"""

import logging
import os
import re
import subprocess
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

_REMOTE_OWNER = re.compile(
    r"(?:[/:])(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)

KIND_LIBRARY = "library"
KIND_GITHUB = "github"
KIND_LOCAL_GIT = "local-git"
KIND_LOCAL = "local"


def remote_owner(url: str) -> Optional[str]:
    """Extract the owner segment from an https/ssh git remote URL."""
    match = _REMOTE_OWNER.search(url.strip())
    return match.group("owner") if match else None


def classify_project(path: str, owned_users: Iterable[str]) -> str:
    if not os.path.isdir(os.path.join(path, ".git")):
        return KIND_LOCAL
    try:
        res = subprocess.run(
            ["git", "-C", path, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return KIND_LOCAL_GIT
    if res.returncode != 0 or not res.stdout.strip():
        return KIND_LOCAL_GIT

    owner = remote_owner(res.stdout)
    if owner is None:
        return KIND_LOCAL_GIT
    owned = {u.strip().lower() for u in owned_users if u.strip()}
    return KIND_GITHUB if owner.lower() in owned else KIND_LIBRARY


def is_modifiable(kind: Optional[str]) -> bool:
    """Libraries are read-only territory for agents."""
    return kind != KIND_LIBRARY
