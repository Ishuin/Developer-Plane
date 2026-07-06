"""Autopilot endpoints: completion scoring, priority queue, agent runs."""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from dcp.core.models import AgentRun, Page
from dcp.cortex.autopilot import AutopilotInProgress

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])
completion_router = APIRouter(prefix="/api/completion", tags=["completion"])


def _state(request: Request):
    return request.app.state.dcp


# ------------------------------------------------------------------ completion
@completion_router.post("/evaluate")
def evaluate(request: Request, path: str):
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Not a directory: {path}")
    return _state(request).completion.evaluate(path).model_dump()


@completion_router.post("/evaluate_all")
def evaluate_all(request: Request):
    """Synchronous sweep over registered projects (heuristic evals are cheap;
    dod.yaml command assertions run with per-command timeouts)."""
    state = _state(request)
    items, _ = state.db.list_projects(limit=100000)
    results = {"evaluated": 0, "errors": 0}
    for project in items:
        try:
            state.completion.evaluate(project.path)
            results["evaluated"] += 1
        except Exception:  # noqa: BLE001
            results["errors"] += 1
    return results


# ----------------------------------------------------------------------- queue
@router.get("/queue")
def queue(request: Request, limit: int = Query(20, ge=1, le=200)):
    return {"queue": [p.model_dump() for p in _state(request).db.autopilot_queue(limit)]}


class EnableRequest(BaseModel):
    path: str
    enabled: bool


@router.post("/enable")
def enable(request: Request, body: EnableRequest):
    state = _state(request)
    if state.db.get_project(body.path) is None:
        raise HTTPException(status_code=404, detail=f"Unknown project: {body.path}")
    state.db.set_automation(body.path, body.enabled)
    return {"path": body.path, "automation_enabled": body.enabled}


# ----------------------------------------------------------------------- batch
class StartRequest(BaseModel):
    limit: int = 3
    paths: Optional[list] = None


@router.post("/start")
def start(request: Request, body: StartRequest = StartRequest()):
    try:
        return _state(request).autopilot.start(limit=body.limit, paths=body.paths)
    except AutopilotInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/status")
def status(request: Request):
    return _state(request).autopilot.status()


# ------------------------------------------------------------------------ runs
@router.get("/runs", response_model=Page[AgentRun])
def runs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    project_id: Optional[str] = None,
):
    db = _state(request).db
    return Page[AgentRun](
        items=db.get_agent_runs(
            limit=page_size, offset=(page - 1) * page_size, project_id=project_id
        ),
        page=page, page_size=page_size,
        total=db.count_agent_runs(project_id),
    )


@router.post("/runs/{run_id}/approve")
def approve(request: Request, run_id: int):
    return _apply_verdict(request, run_id, "approved")


@router.post("/runs/{run_id}/discard")
def discard(request: Request, run_id: int):
    return _apply_verdict(request, run_id, "discarded")


def _apply_verdict(request: Request, run_id: int, verdict: str):
    try:
        return _state(request).autopilot.apply_verdict(run_id, verdict)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
