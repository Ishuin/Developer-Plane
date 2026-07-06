"""Project discovery: walk a root, find project roots, register them."""

import logging
import os
from typing import Callable, List, Optional, Set

from dcp.core.bus import EventBus, bus as default_bus
from dcp.core.models import Project
from dcp.database import EventSourcingDB
from dcp.sentry.classify import classify_project
from dcp.sentry.detectors import STRONG_INDICATORS, detect

logger = logging.getLogger(__name__)

# Directories that belong to a project's internals, never a project themselves.
# Matched case-insensitively (Windows: Lib == lib).
EXCLUDED_DIRS: Set[str] = {
    # build output
    "build", "dist", "out", "target", "bin", "obj", "debug", "release",
    ".next", ".nuxt", ".output", ".cache", ".wrangler",
    # sources / internals
    "src", "source", "sources", "lib", "libs", "packages", "modules",
    "internal", "include", "app", "apps", "components", "resources",
    "test", "tests", "__tests__", "e2e", "specs", "spec",
    "utils", "util", "helpers", "common", "shared", "scripts", "tools",
    "docs", "doc", "documentation", "examples", "example", "demo", "samples",
    "config", "configs", "settings", "assets", "static", "public", "media",
    "images", "img", "styles", "types", "typings", "migrations",
    # OS / distro layout (MSYS2, unix-like trees, SDKs)
    "usr", "share", "etc", "opt", "sdk", "sysroot",
    "completions", "readline", "html", "_static", "i18n", "tcl", "pref",
    # caches, deps, envs
    "node_modules", "vendor", "third_party", "__pycache__",
    "venv", "venvs", "virtualenv", "env", "site-packages", "dist-packages",
    ".pytest_cache", "pods", "carthage",
    # misc
    "temp", "tmp", "backup", "backups", "old", "archive",
}

# Ancestor path segments that mark an entire tree as tool/system territory.
SYSTEM_TREE_SEGMENTS: Set[str] = {
    "program files", "program files (x86)", "programdata", "windows",
    "appdata", "$recycle.bin", "system volume information",
    "msys2", "msys64", "mingw32", "mingw64", "cygwin", "cygwin64",
    "scoop", "chocolatey", "anaconda3", "miniconda3",
}



class ProjectDiscovery:
    """Scans the filesystem for project roots and records them as signals."""

    def __init__(
        self,
        db: EventSourcingDB,
        event_bus: Optional[EventBus] = None,
        owned_users: Optional[List[str]] = None,
    ):
        self.db = db
        self.bus = event_bus or default_bus
        self.owned_users = owned_users or []

    def scan(
        self,
        root: str = ".",
        max_depth: int = 6,
        on_found: Optional[Callable[[Project], None]] = None,
    ) -> List[Project]:
        """Walk `root` and register projects incrementally.

        Each accepted project is upserted and announced the moment it is
        found (os.walk is top-down, so parents are always seen before
        children — nested dedupe happens inline). `on_found` lets callers
        stream progress.
        """
        root = os.path.abspath(root)
        kept: List[Project] = []
        kept_paths: List[str] = []

        for current, dirs, files in os.walk(root):
            rel = os.path.relpath(current, root)
            depth = rel.count(os.sep)
            # System-tree check applies only to segments below the scan
            # root — the user's chosen root is trusted as-is.
            if depth >= max_depth or self._in_system_tree(rel):
                dirs[:] = []
                continue

            has_git = ".git" in dirs
            # Never descend into project internals, dot-dirs, or system trees.
            dirs[:] = sorted(
                d for d in dirs
                if d.lower() not in EXCLUDED_DIRS
                and not d.startswith(".")
                and d.lower() not in SYSTEM_TREE_SEGMENTS
            )

            file_set = set(files) | ({".git"} if has_git else set())
            has_strong = bool(file_set & STRONG_INDICATORS)
            project_type = detect(files)

            if not has_strong and project_type == "Unknown":
                continue

            inside_kept = any(
                current.startswith(kp + os.sep) for kp in kept_paths
            )
            if inside_kept and not has_git:
                # Inside a known project: only a directory with its own git
                # repo counts as a separate (monorepo) project. Manifests
                # like CMakeLists.txt or pyproject.toml alone do not — every
                # large project has those in subdirectories.
                if not has_strong:
                    dirs[:] = []  # plain internals — stop descending
                continue
            if not has_strong:
                # Heuristic-only root — don't treat its children as projects.
                dirs[:] = []

            project = Project(path=current, type=project_type)
            kept.append(project)
            kept_paths.append(current)
            self._register(project)
            if on_found:
                on_found(project)

        logger.info("Discovery: %d project(s) under %s", len(kept), root)
        return kept

    @staticmethod
    def _in_system_tree(path: str) -> bool:
        """True when any path segment marks tool/system territory."""
        return any(
            segment.lower() in SYSTEM_TREE_SEGMENTS
            for segment in path.replace("/", os.sep).split(os.sep)
        )

    def _register(self, project: Project) -> None:
        self.db.upsert_project(project.path, project.type)
        project.kind = classify_project(project.path, self.owned_users)
        self.db.set_project_kind(project.path, project.kind)
        self.db.log_signal(
            "ProjectDiscovered",
            {"path": project.path, "type": project.type},
            project_id=project.path,
        )
        self.bus.publish(
            "ProjectDiscovered", {"path": project.path, "type": project.type}
        )
