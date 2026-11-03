"""Demo mode: an isolated database plus a workspace of small real git repos.

`python src/main.py --demo` points the control plane at ~/.dcp/demo, so the
normal database, scan root and agent mode are never touched. Dropping the
flag returns to the regular setup.
"""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List

DEMO_HOME = Path.home() / ".dcp" / "demo"
DEMO_WORKSPACE = DEMO_HOME / "workspace"
DEMO_DB = DEMO_HOME / "demo.db"
DEMO_ENV_FLAG = "DCP_DEMO"
STALE_COMMIT_DATE = "2025-01-10T10:00:00"
SCOPE_NOTE = "Edit only the source file; leave README, CI and config untouched."
AUTOPILOT_TASKS = {
    "todo-cli": f"Fix Todo.complete() so test_complete_marks_done passes. {SCOPE_NOTE}",
    "text-utils": f"Implement slugify(s) in text_utils.py so the tests pass. {SCOPE_NOTE}",
}
OPEN_TASK_STATUSES = ("todo", "in_progress", "review")
GIT_IDENTITY = ("-c", "user.email=demo@dcp.local", "-c", "user.name=DCP Demo")

Files = Dict[str, str]


def apply_demo_env() -> None:
    """Force the demo settings for this process only (no files are modified)."""
    DEMO_HOME.mkdir(parents=True, exist_ok=True)
    os.environ[DEMO_ENV_FLAG] = "1"
    os.environ["DCP_DB_PATH"] = str(DEMO_DB)
    os.environ["DCP_SCAN_ROOT"] = str(DEMO_WORKSPACE)
    os.environ["DCP_AGENT_MODE"] = "native"
    os.environ["DCP_AUTO_ANALYZE"] = "1"
    os.environ.pop("DCP_WATCH_ROOTS", None)


def _force_remove(func, path, *_exc) -> None:
    """rmtree error hook: git object files are read-only on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def reset_demo() -> None:
    """Delete the demo database and workspace so they are rebuilt fresh."""
    if not DEMO_HOME.exists():
        return
    hook = {"onexc": _force_remove} if sys.version_info >= (3, 12) else {"onerror": _force_remove}
    shutil.rmtree(DEMO_HOME, **hook)


def _git(path: Path, *args: str, date: str = "") -> None:
    """Run a git command in path, optionally pinning the commit date."""
    env = dict(os.environ)
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    subprocess.run(["git", "-C", str(path), *GIT_IDENTITY, *args],
                   capture_output=True, check=True, env=env)


def _write_files(path: Path, files: Files) -> None:
    """Write relative-path -> content pairs under path."""
    for rel, content in files.items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _make_project(name: str, files: Files, git: bool = True, date: str = "") -> None:
    """Create one demo project; skip if it already exists."""
    path = DEMO_WORKSPACE / name
    if path.exists():
        return
    path.mkdir(parents=True)
    _write_files(path, files)
    if git:
        # Keeps the generated status report from showing up as a dirty tree.
        (path / ".gitignore").write_text("project_status.md\n", encoding="utf-8")
        _git(path, "init", "-q")
        _git(path, "add", "-A")
        _git(path, "commit", "-qm", "Initial commit", date=date)


PYTEST_CI = ("name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
             "    steps:\n      - uses: actions/checkout@v4\n      - run: pip install pytest && pytest -q\n")

_PROJECTS: List[Callable[[], None]] = []


def _project(fn: Callable[[], None]) -> Callable[[], None]:
    """Register a project builder."""
    _PROJECTS.append(fn)
    return fn


@_project
def _invoice_api() -> None:
    _make_project("invoice-api", {
        "README.md": "# invoice-api\n\nSmall invoicing service.\n",
        "requirements.txt": "fastapi\n",
        "Dockerfile": "FROM python:3.12-slim\nCOPY . /app\nCMD [\"python\", \"/app/app.py\"]\n",
        ".github/workflows/ci.yml": PYTEST_CI,
        "app.py": "def total(items):\n    return sum(i['price'] * i['qty'] for i in items)\n",
        "tests/test_app.py": "from app import total\n\n\ndef test_total():\n    assert total([{'price': 2, 'qty': 3}]) == 6\n",
    })


@_project
def _todo_cli() -> None:
    _make_project("todo-cli", {
        "README.md": "# todo-cli\n\nTiny todo list. `complete()` should mark a task done.\n",
        "requirements.txt": "",
        "todo.py": ("class Todo:\n    def __init__(self):\n        self.tasks = {}\n\n"
                    "    def add(self, title):\n        self.tasks[title] = False\n\n"
                    "    def complete(self, title):\n        self.tasks[title] = False\n\n"
                    "    def pending(self):\n        return [t for t, done in self.tasks.items() if not done]\n"),
        "tests/test_todo.py": ("from todo import Todo\n\n\ndef test_complete_marks_done():\n"
                               "    t = Todo()\n    t.add('a')\n    t.complete('a')\n    assert t.pending() == []\n"),
    })


@_project
def _text_utils() -> None:
    _make_project("text-utils", {
        "README.md": "# text-utils\n\nHelpers: `shout(s)` upper-cases; `slugify(s)` is planned (lowercase, spaces to dashes).\n",
        "requirements.txt": "",
        "text_utils.py": "def shout(s):\n    return s.upper()\n\n\n# TODO: add slugify(s)\n",
        "tests/test_text_utils.py": ("from text_utils import shout, slugify\n\n\ndef test_shout():\n"
                                     "    assert shout('hi') == 'HI'\n\n\ndef test_slugify():\n"
                                     "    assert slugify('Hello World') == 'hello-world'\n"),
    })


@_project
def _weather_dashboard() -> None:
    _make_project("weather-dashboard", {
        "README.md": "# weather-dashboard\n\nCity weather widgets.\n",
        "package.json": '{"name": "weather-dashboard", "version": "0.2.0"}\n',
        "src/index.js": "console.log('weather');\n",
        "test/index.test.js": "// TODO: write tests\n",
    })


@_project
def _landing_page() -> None:
    _make_project("landing-page", {
        "README.md": "# landing-page\n\nMarketing site.\n",
        "index.html": "<h1>Welcome</h1>\n",
        "Dockerfile": "FROM nginx:alpine\nCOPY index.html /usr/share/nginx/html/\n",
        ".github/workflows/ci.yml": "name: ci\non: [push]\njobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n",
    })


@_project
def _ml_experiments() -> None:
    _make_project("ml-experiments", {
        "requirements.txt": "scikit-learn\n",
        "notes.md": "Ideas: try gradient boosting on the churn data.\n",
        "explore.ipynb": '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}\n',
    }, git=False)


@_project
def _legacy_blog() -> None:
    _make_project("legacy-blog", {
        "README.md": "# legacy-blog\n\nOld static blog.\n",
        "index.html": "<h1>My 2024 blog</h1>\n",
    }, date=STALE_COMMIT_DATE)


def build_demo_workspace() -> List[str]:
    """Create any missing demo projects and return the workspace path list."""
    DEMO_WORKSPACE.mkdir(parents=True, exist_ok=True)
    for build in _PROJECTS:
        build()
    return sorted(str(p) for p in DEMO_WORKSPACE.iterdir() if p.is_dir())


def _focus_board(state, path: str, title: str) -> None:
    """Replace the generic analysis cards with one small, demo-friendly task."""
    for task in state.db.list_tasks(project_id=path, limit=500):
        if task.status in OPEN_TASK_STATUSES:
            state.db.update_task(task.id, status="discarded")
    state.tasks.seed(path, [title], origin="demo")


def seed_demo_state(state) -> None:
    """Scan, analyze and arm the autopilot targets (blocking, ~seconds)."""
    state.discovery.scan(str(DEMO_WORKSPACE))
    state.analysis.start()
    state.analysis.wait()
    for project in state.db.list_projects(limit=1000)[0]:
        state.completion.evaluate(project.path)
        task_title = AUTOPILOT_TASKS.get(Path(project.path).name)
        if task_title:
            _focus_board(state, project.path, task_title)
            state.db.set_automation(project.path, True)
