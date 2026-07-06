"""Task board + self-improvement endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
self_router = APIRouter(prefix="/api/self", tags=["self-improvement"])


def _state(request: Request):
    return request.app.state.dcp


# ----------------------------------------------------------------------- board
@router.get("/board")
def board(
    request: Request,
    project: Optional[str] = None,
    pipeline: str = Query("project", pattern="^(project|self)$"),
):
    return _state(request).tasks.board(project_id=project, pipeline=pipeline)


@router.post("/{task_id}/discard")
def discard(request: Request, task_id: int):
    """User emergency override — removes the card from the flow."""
    try:
        return _state(request).tasks.discard(task_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{task_id}/move")
def move(
    request: Request,
    task_id: int,
    status: str = Query(..., pattern="^(todo|in_progress|review|done)$"),
):
    """Manual card move (normally agents do this)."""
    try:
        return _state(request).tasks.move(
            task_id, status, actor="user"
        ).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# -------------------------------------------------------------- classification
@router.post("/classify_all")
def classify_all(request: Request):
    """Re-classify every registered project (library / github / local…)."""
    from dcp.sentry.classify import classify_project

    state = _state(request)
    owned = [u.strip() for u in state.settings.github_users.split(",") if u.strip()]
    items, _ = state.db.list_projects(limit=100000)
    counts: dict = {}
    for project in items:
        kind = classify_project(project.path, owned)
        state.db.set_project_kind(project.path, kind)
        counts[kind] = counts.get(kind, 0) + 1
    return {"classified": len(items), "by_kind": counts}


# ------------------------------------------------------------ self-improvement
@self_router.get("/status")
def self_status(request: Request):
    return _state(request).self_improvement.status()


@self_router.get("/tasks")
def self_tasks(request: Request):
    state = _state(request)
    return state.tasks.board(project_id=state.self_improvement.home_path,
                             pipeline="self")


@self_router.post("/check")
def self_check(request: Request):
    """Run the daily check now (executes at most one task if due)."""
    return _state(request).self_improvement.maybe_run_daily()
