"""Provider-agnostic chat model factory (Anthropic and OpenAI-compatible).

Lazy-imports the provider SDK so the control plane runs without them
installed (AI-Optional principle).
"""

from typing import Any, Dict

from dcp.agents.base import AgentUnavailable
from dcp.config import Settings

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENAI = "openai"
PROVIDERS = (PROVIDER_ANTHROPIC, PROVIDER_OPENAI)

ANTHROPIC_MAX_TOKENS = 1024
CONNECTION_TEST_PROMPT = "Reply with the single word: OK"
CONNECTION_TEST_REPLY_LIMIT = 80


def _require_credentials(settings: Settings) -> None:
    """Raise AgentUnavailable unless the AI tier is enabled and configured."""
    if not settings.ai_enabled:
        raise AgentUnavailable("AI tier disabled (enable it in Settings or set DCP_AI_ENABLED=1)")
    if settings.llm_provider not in PROVIDERS:
        raise AgentUnavailable(f"Unknown LLM provider: {settings.llm_provider!r}")
    if not (settings.llm_api_key and settings.llm_model):
        raise AgentUnavailable("LLM credentials missing (DCP_LLM_API_KEY / DCP_LLM_MODEL)")


def _build_anthropic(settings: Settings):
    """Build a ChatAnthropic client."""
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:
        raise AgentUnavailable("langchain-anthropic not installed") from exc
    kwargs: Dict[str, Any] = {
        "model": settings.llm_model,
        "api_key": settings.llm_api_key,
        "max_tokens": ANTHROPIC_MAX_TOKENS,
    }
    if settings.llm_api_base:
        kwargs["base_url"] = settings.llm_api_base
    return ChatAnthropic(**kwargs)


def _build_openai(settings: Settings):
    """Build a ChatOpenAI client; llm_api_base targets any OpenAI-compatible host."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise AgentUnavailable("langchain-openai not installed") from exc
    kwargs: Dict[str, Any] = {
        "model": settings.llm_model,
        "api_key": settings.llm_api_key,
    }
    if settings.llm_api_base:
        kwargs["base_url"] = settings.llm_api_base
    return ChatOpenAI(**kwargs)


def build_chat_model(settings: Settings):
    """Return a LangChain chat model for the configured provider."""
    _require_credentials(settings)
    if settings.llm_provider == PROVIDER_ANTHROPIC:
        return _build_anthropic(settings)
    return _build_openai(settings)


def message_text(content) -> str:
    """Plain text of a model reply; providers may return typed content blocks."""
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "") for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def check_connection(settings: Settings) -> str:
    """Send a tiny prompt and return the (truncated) reply.

    Raises AgentUnavailable for config problems; provider errors propagate
    to the caller, which is responsible for redacting secrets.
    """
    reply = build_chat_model(settings).invoke(CONNECTION_TEST_PROMPT).content
    return message_text(reply).strip()[:CONNECTION_TEST_REPLY_LIMIT]
