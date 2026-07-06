"""Project endpoints: paginated listing, scan, genome, stage, context."""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from dcp.core.models import Page, Project
from dcp.sentry import ScanInProgress
from dcp.sentry.genome import build_genome

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _state(request: Request):
    return request.app.state.dcp


@router.get("", response_model=Page[Project])
def list_projects(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(0, ge=0),
    search: Optional[str] = None,
    type: Optional[str] = None,
):
    state = _state(request)
    if page_size <= 0:
        page_size = state.settings.default_page_size
    page_size = min(page_size, state.settings.max_page_size)
    items, total = state.db.list_projects(
        limit=page_size,
        offset=(page - 1) * page_size,
        search=search,
        project_type=type,
    )
    return Page[Project](items=items, page=page, page_size=page_size, total=total)


@router.get("/types")
def list_types(request: Request):
    return {"types": _state(request).db.project_types()}


@router.delete("")
def clear_projects(request: Request):
    """Clear the project registry (event log is untouched)."""
    removed = _state(request).db.clear_projects()
    return {"removed": removed}


@router.post("/scan")
def scan(request: Request, path: Optional[str] = None, wait: bool = False):
    """Start a discovery scan.

    Default is asynchronous: returns immediately with job status; poll
    GET /api/projects/scan/status and the paginated listing for live
    results. `wait=true` blocks until the scan finishes (CLI/tests).
    """
    state = _state(request)
    root = path or state.settings.scan_root
    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")
    if wait:
        projects = state.discovery.scan(root)
        return {"scanned": os.path.abspath(root), "found": len(projects),
                "running": False}
    try:
        status = state.scanner.start(root)
    except ScanInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return status


@router.get("/scan/status")
def scan_status(request: Request):
    return _state(request).scanner.status()


@router.get("/genome")
def genome(request: Request, path: str):
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Not a directory: {path}")
    return build_genome(path).model_dump()


@router.get("/stage")
def stage(request: Request, path: str):
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Not a directory: {path}")
    return _state(request).inference.infer_stage(path).model_dump()


@router.get("/context")
def context(request: Request, path: str, as_prompt: bool = False):
    state = _state(request)
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Not a directory: {path}")
    stage_result = state.inference.infer_stage(path)
    payload = state.assembler.assemble(path, stage=stage_result)
    if as_prompt:
        return {"prompt": state.assembler.to_prompt(payload)}
    return payload
