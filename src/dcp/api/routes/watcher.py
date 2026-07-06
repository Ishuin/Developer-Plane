"""Watcher control endpoints: start/stop/status of the Sentry watcher."""

import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/watcher", tags=["watcher"])


class WatchRequest(BaseModel):
    path: str = "."


@router.get("")
def status(request: Request):
    return {"running": request.app.state.dcp.watcher.is_running}


@router.post("/start")
def start(request: Request, body: WatchRequest):
    if not os.path.isdir(body.path):
        raise HTTPException(status_code=400, detail=f"Not a directory: {body.path}")
    request.app.state.dcp.watcher.start(body.path)
    return {"running": True, "path": os.path.abspath(body.path)}


@router.post("/stop")
def stop(request: Request):
    request.app.state.dcp.watcher.stop()
    return {"running": False}
