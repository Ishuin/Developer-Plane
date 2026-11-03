"""Agent-mode endpoints: choose the CLI or the built-in native agent."""

from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel, field_validator

from dcp.agents.mode_executor import AGENT_MODES
from dcp.envfile import write_env_values

router = APIRouter(prefix="/api/settings/agent", tags=["settings"])


class AgentModeUpdate(BaseModel):
    mode: str

    @field_validator("mode")
    @classmethod
    def _known_mode(cls, value: str) -> str:
        if value not in AGENT_MODES:
            raise ValueError(f"mode must be one of {', '.join(AGENT_MODES)}")
        return value


def _view(settings) -> dict:
    return {"mode": settings.agent_mode, "modes": list(AGENT_MODES),
            "demo": settings.demo_mode}


@router.get("")
def read_mode(request: Request):
    return _view(request.app.state.dcp.settings)


@router.put("")
def update_mode(request: Request, body: AgentModeUpdate):
    settings = request.app.state.dcp.settings
    settings.agent_mode = body.mode
    # Demo mode is session-only so switching back to normal needs no cleanup.
    if not settings.demo_mode:
        write_env_values(Path(settings.env_file), {"DCP_AGENT_MODE": body.mode})
    return _view(settings)
