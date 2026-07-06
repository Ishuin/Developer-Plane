"""Agent endpoints: list registered agents, run one against a project."""

import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from dcp.agents.base import AgentUnavailable

router = APIRouter(prefix="/api/agents", tags=["agents"])


class RunRequest(BaseModel):
    agent: str
    path: str


@router.get("")
def list_agents(request: Request):
    return {"agents": request.app.state.dcp.router.available()}


@router.post("/run")
def run_agent(request: Request, body: RunRequest):
    state = request.app.state.dcp
    if not os.path.isdir(body.path):
        raise HTTPException(status_code=404, detail=f"Not a directory: {body.path}")
    stage = state.inference.infer_stage(body.path)
    context = state.assembler.assemble(body.path, stage=stage)
    try:
        result = state.router.run(body.agent, context)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.model_dump()
