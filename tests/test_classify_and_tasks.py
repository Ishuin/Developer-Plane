"""Tests for project classification and the kanban task service."""

import subprocess

import pytest

from dcp.core.models import Task
from dcp.cortex.tasks import TaskService
from dcp.sentry.classify import (
    KIND_GITHUB, KIND_LIBRARY, KIND_LOCAL, KIND_LOCAL_GIT,
    classify_project, is_modifiable, remote_owner,
)

OWNED = ["Ishuin"]


def git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], capture_output=True, check=True)


def make_repo(tmp_path, name, remote=None):
    proj = tmp_path / name
    proj.mkdir()
    (proj / "x.py").write_text("pass\n")
    git(proj, "init", "-q")
    if remote:
        git(proj, "remote", "add", "origin", remote)
    return proj


# ------------------------------------------------------------------- classify
def test_remote_owner_parsing():
    assert remote_owner("https://github.com/Ishuin/Developer-Plane.git") == "Ishuin"
    assert remote_owner("git@github.com:ggerganov/llama.cpp.git") == "ggerganov"
    assert remote_owner("https://gitlab.com/someone/repo") == "someone"
    assert remote_owner("not-a-url") is None


def test_classify_no_git_is_local(tmp_path):
    proj = tmp_path / "plain"
    proj.mkdir()
    assert classify_project(str(proj), OWNED) == KIND_LOCAL


def test_classify_git_without_remote_is_local_git(tmp_path):
    proj = make_repo(tmp_path, "own_local")
    assert classify_project(str(proj), OWNED) == KIND_LOCAL_GIT


def test_classify_owned_remote_is_github(tmp_path):
    proj = make_repo(tmp_path, "mine",
                     remote="https://github.com/Ishuin/mine.git")
    assert classify_project(str(proj), OWNED) == KIND_GITHUB


def test_classify_foreign_remote_is_library(tmp_path):
    proj = make_repo(tmp_path, "clone",
                     remote="https://github.com/ggerganov/llama.cpp.git")
    assert classify_project(str(proj), OWNED) == KIND_LIBRARY
    assert not is_modifiable(KIND_LIBRARY)
    assert is_modifiable(KIND_GITHUB) and is_modifiable(None)


def test_scan_stores_kind(db, sample_tree):
    from dcp.sentry.discovery import ProjectDiscovery

    ProjectDiscovery(db, owned_users=OWNED).scan(str(sample_tree))
    items, _ = db.list_projects(limit=50)
    assert all(p.kind is not None for p in items)
    py_proj = next(p for p in items if p.path.endswith("py_proj"))
    assert py_proj.kind == KIND_LOCAL  # no .git in the fixture project


# ---------------------------------------------------------------------- tasks
@pytest.fixture
def svc(db):
    return TaskService(db)


def test_seed_dedupes_open_titles(db, svc):
    created = svc.seed("/p/a", ["Add tests", "Add CI"], origin="analysis")
    assert len(created) == 2
    again = svc.seed("/p/a", ["Add tests", "Add docs"], origin="analysis")
    assert [t.title for t in again] == ["Add docs"]


def test_move_lifecycle_and_log(db, svc):
    task = svc.seed("/p/b", ["Fix bug"], origin="analysis")[0]
    svc.move(task.id, "in_progress", run_id=7)
    svc.move(task.id, "review", run_id=7)
    final = svc.move(task.id, "done", actor="verdict")
    assert final.status == "done" and final.run_id == 7
    moves = [d for d in db.get_decisions(limit=20) if d.decision_type == "TaskMoved"]
    assert len(moves) == 3


def test_user_discard_is_terminal(db, svc):
    task = svc.seed("/p/c", ["Risky change"], origin="analysis")[0]
    svc.discard(task.id)
    assert db.get_task(task.id).status == "discarded"
    with pytest.raises(ValueError):
        svc.move(task.id, "todo")  # discarded cards never come back


def test_board_groups_by_status(db, svc):
    a, b = svc.seed("/p/d", ["One", "Two"], origin="analysis")
    svc.move(a.id, "review")
    board = svc.board(project_id="/p/d")
    assert [t["title"] for t in board["review"]] == ["One"]
    assert [t["title"] for t in board["todo"]] == ["Two"]
    assert board["done"] == []


def test_invalid_move_rejected(db, svc):
    task = svc.seed("/p/e", ["X"], origin="analysis")[0]
    with pytest.raises(ValueError):
        svc.move(task.id, "nonsense")
    with pytest.raises(KeyError):
        svc.move(99999, "done")
