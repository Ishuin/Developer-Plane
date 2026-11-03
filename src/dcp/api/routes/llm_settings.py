"""LLM settings endpoints: view (key masked), update, and test the connection."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from dcp.agents.base import AgentUnavailable
from dcp.config import Settings
from dcp.envfile import write_env_values
from dcp.llm import PROVIDERS, check_connection

router = APIRouter(prefix="/api/settings/llm", tags=["settings"])

KEY_TAIL_LENGTH = 4
URL_SCHEMES = ("http://", "https://")
FORBIDDEN_CHARS = ("\r", "\n", "\0")


class LlmSettingsUpdate(BaseModel):
    """Payload for updating LLM config. api_key None keeps it; "" clears it."""

    provider: str
    model: str
    api_base: str = ""
    api_key: Optional[str] = None
    enabled: bool = True

    @field_validator("provider", "model", "api_base", "api_key")
    @classmethod
    def _no_control_chars(cls, value):
        if value and any(c in value for c in FORBIDDEN_CHARS):
            raise ValueError("control characters are not allowed")
        return value

    @field_validator("provider")
    @classmethod
    def _known_provider(cls, value: str) -> str:
        if value not in PROVIDERS:
            raise ValueError(f"provider must be one of {', '.join(PROVIDERS)}")
        return value

    @field_validator("model")
    @classmethod
    def _model_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("model is required")
        return value.strip()

    @field_validator("api_base")
    @classmethod
    def _valid_base_url(cls, value: str) -> str:
        value = value.strip()
        if value and not value.startswith(URL_SCHEMES):
            raise ValueError("api_base must start with http:// or https://")
        return value


def _public_view(settings: Settings) -> dict:
    """Settings as exposed to the UI: never includes the key itself."""
    key = settings.llm_api_key
    return {
        "enabled": settings.ai_enabled,
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "api_base": settings.llm_api_base,
        "has_key": bool(key),
        "key_hint": f"…{key[-KEY_TAIL_LENGTH:]}" if len(key) > KEY_TAIL_LENGTH else "",
        "providers": list(PROVIDERS),
    }


def _redact(message: str, secret: str) -> str:
    """Strip the API key from provider error text before returning it."""
    return message.replace(secret, "***") if secret else message


@router.get("")
def read_settings(request: Request):
    return _public_view(request.app.state.dcp.settings)


@router.put("")
def update_settings(request: Request, body: LlmSettingsUpdate):
    settings: Settings = request.app.state.dcp.settings
    endpoint_changed = (body.provider != settings.llm_provider
                        or body.api_base != settings.llm_api_base)
    # A saved key must not be redirected to a new endpoint without re-entry.
    if endpoint_changed and settings.llm_api_key and not body.api_key:
        raise HTTPException(
            status_code=400,
            detail="Re-enter the API key when changing provider or base URL",
        )
    if body.api_key is not None:
        settings.llm_api_key = body.api_key.strip()
    settings.ai_enabled = body.enabled
    settings.llm_provider = body.provider
    settings.llm_model = body.model
    settings.llm_api_base = body.api_base
    write_env_values(Path(settings.env_file), {
        "DCP_AI_ENABLED": "1" if settings.ai_enabled else "0",
        "DCP_LLM_PROVIDER": settings.llm_provider,
        "DCP_LLM_MODEL": settings.llm_model,
        "DCP_LLM_API_BASE": settings.llm_api_base,
        "DCP_LLM_API_KEY": settings.llm_api_key,
    })
    return _public_view(settings)


@router.post("/test")
def test_connection(request: Request):
    settings: Settings = request.app.state.dcp.settings
    try:
        reply = check_connection(settings)
    except AgentUnavailable as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # provider SDKs raise many unrelated types
        detail = _redact(f"{type(exc).__name__}: {exc}", settings.llm_api_key)
        raise HTTPException(status_code=502, detail=detail)
    return {"ok": True, "reply": reply}
