"""WIP triage endpoints: review, test, and resolve uncommitted changes
without leaving the dashboard."""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from dcp.agents import gitops

router = APIRouter(prefix="/api/wip", tags=["wip"])


def _check(request: Request, path: str) -> None:
    """WIP operations are limited to projects registered by discovery —
    never arbitrary filesystem paths from the network."""
    if request.app.state.dcp.db.get_project(path) is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown project — only registered projects can be triaged",
        )
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Not a directory: {path}")
    if not gitops.is_repo(path):
        raise HTTPException(status_code=400, detail="Not a git repository")


@router.get("")
def wip_overview(request: Request, path: str):
    _check(request, path)
    return {
        "path": path,
        "branch": gitops.current_branch(path),
        "files": gitops.dirty_files(path),
        "remote": gitops.remote_url(path),
        "github": gitops.github_repo_slug(path),
        "test_command": gitops.detect_test_command(path),
    }


@router.get("/diff")
def wip_diff(request: Request, path: str):
    _check(request, path)
    return {"diff": gitops.diff_text(path)}


class TestRequest(BaseModel):
    path: str


@router.post("/test")
def wip_test(request: Request, body: TestRequest):
    """Runs ONLY the auto-detected test command (dod.yaml / pytest / npm /
    cargo / go). Arbitrary commands from the network are not accepted."""
    _check(request, body.path)
    result = gitops.run_tests(body.path)
    request.app.state.dcp.db.log_signal(
        "WipTestRun", {k: v for k, v in result.items() if k != "output"},
        project_id=body.path,
    )
    return result


class CommitRequest(BaseModel):
    path: str
    message: str = ""
    branch: Optional[str] = None
    push: bool = True


@router.post("/commit")
def wip_commit(request: Request, body: CommitRequest):
    _check(request, body.path)
    try:
        branch, sha = gitops.commit_wip_to_branch(
            body.path, body.message, body.branch
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    result = {"branch": branch, "sha": sha, "pushed": False}
    if body.push:
        result.update(gitops.push_branch(body.path, branch))

    db = request.app.state.dcp.db
    db.log_decision(
        "WipCommitted",
        {"branch": branch, "sha": sha, "pushed": result.get("pushed"),
         "pr_url": result.get("pr_url")},
        project_id=body.path,
    )
    # Tree is clean now — refresh the completion score right away.
    request.app.state.dcp.completion.evaluate(body.path)
    return result


class DiscardRequest(BaseModel):
    path: str
    confirm: bool = False


@router.post("/discard")
def wip_discard(request: Request, body: DiscardRequest):
    _check(request, body.path)
    if not body.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required")
    try:
        result = gitops.discard_all_wip(body.path)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db = request.app.state.dcp.db
    db.log_decision("WipDiscarded", result, project_id=body.path)
    request.app.state.dcp.completion.evaluate(body.path)
    return result
