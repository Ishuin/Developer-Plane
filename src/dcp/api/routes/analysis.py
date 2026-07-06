"""Analysis endpoints: batch status analysis + per-project report access."""

import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from dcp.cortex import AnalysisInProgress
from dcp.cortex.analysis import STATUS_FILENAME

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class AnalysisRequest(BaseModel):
    paths: Optional[List[str]] = None


@router.post("/start")
def start(request: Request, body: AnalysisRequest = AnalysisRequest()):
    """Start a batch. Empty/omitted paths = every registered project."""
    state = request.app.state.dcp
    try:
        return state.analysis.start(body.paths)
    except AnalysisInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/status")
def status(request: Request):
    return request.app.state.dcp.analysis.status()


@router.post("/project")
def analyze_project(request: Request, path: str):
    """Analyze one project synchronously and return its status."""
    state = request.app.state.dcp
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Not a directory: {path}")
    result = state.analysis.analyze_one(path)
    return result.model_dump()


@router.get("/report", response_class=PlainTextResponse)
def report(request: Request, path: str):
    """Return a project's project_status.md content."""
    report_path = os.path.join(path, STATUS_FILENAME)
    if not os.path.isfile(report_path):
        raise HTTPException(status_code=404, detail="No status report yet")
    with open(report_path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()
