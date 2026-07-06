"""Central configuration for the Developer Control Plane."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    """Runtime settings. Everything is overridable via environment variables."""

    db_path: str = field(
        default_factory=lambda: os.environ.get("DCP_DB_PATH", "context_fabric.db")
    )
    scan_root: str = field(
        default_factory=lambda: os.environ.get("DCP_SCAN_ROOT", ".")
    )
    default_page_size: int = field(
        default_factory=lambda: int(os.environ.get("DCP_PAGE_SIZE", "25"))
    )
    max_page_size: int = 200

    # AI tier. Tier 0 = deterministic heuristics only (always available).
    # Tier 1 = LangChain/LangGraph agents, enabled only when configured.
    ai_enabled: bool = field(
        default_factory=lambda: os.environ.get("DCP_AI_ENABLED", "0") == "1"
    )
    llm_api_base: str = field(
        default_factory=lambda: os.environ.get("DCP_LLM_API_BASE", "")
    )
    llm_api_key: str = field(
        default_factory=lambda: os.environ.get("DCP_LLM_API_KEY", "")
    )
    llm_model: str = field(
        default_factory=lambda: os.environ.get("DCP_LLM_MODEL", "")
    )

    # Parallel workers for the project status analysis batch.
    analysis_workers: int = field(
        default_factory=lambda: int(os.environ.get("DCP_ANALYSIS_WORKERS", "4"))
    )

    # Confidence decay: stage confidence halves after this many idle days.
    confidence_half_life_days: float = field(
        default_factory=lambda: float(os.environ.get("DCP_HALF_LIFE_DAYS", "14"))
    )

    @property
    def web_dir(self) -> Path:
        return Path(__file__).parent / "interfaces" / "web"


def get_settings() -> Settings:
    return Settings()
