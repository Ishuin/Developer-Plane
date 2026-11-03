"""Central configuration for the Developer Control Plane."""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _default_db_path() -> str:
    """Stable default database location.

    Order: explicit env var → a legacy context_fabric.db in the current
    directory (pre-0.2 behaviour, keeps existing data working) → a single
    canonical copy under ~/.dcp so running the tool from different
    directories never scatters databases around.
    """
    env = os.environ.get("DCP_DB_PATH")
    if env:
        return env
    legacy = Path.cwd() / "context_fabric.db"
    if legacy.is_file():
        return str(legacy)
    return str(Path.home() / ".dcp" / "context_fabric.db")


@dataclass
class Settings:
    """Runtime settings. Everything is overridable via environment variables."""

    db_path: str = field(default_factory=_default_db_path)
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
    llm_provider: str = field(
        default_factory=lambda: os.environ.get("DCP_LLM_PROVIDER", "openai")
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

    # Comma-separated roots to auto-watch on server start ("" = off).
    watch_roots: str = field(
        default_factory=lambda: os.environ.get("DCP_WATCH_ROOTS", "")
    )

    # Parallel workers for the project status analysis batch.
    analysis_workers: int = field(
        default_factory=lambda: int(os.environ.get("DCP_ANALYSIS_WORKERS", "4"))
    )

    # GitHub accounts that mark a project as the user's own (comma-separated).
    github_users: str = field(
        default_factory=lambda: os.environ.get("DCP_GITHUB_USERS", "Ishuin")
    )

    # Autopilot: headless coding-agent command template. The task brief is
    # piped to the command via stdin. If the template contains {brief_file},
    # the brief is instead written to a file inside the project directory
    # and the placeholder replaced with its path.
    agent_cmd: str = field(
        default_factory=lambda: os.environ.get(
            "DCP_AGENT_CMD",
            "claude -p --permission-mode acceptEdits",
        )
    )
    # Demo mode (set by `main.py --demo`) and scan-triggered analysis.
    demo_mode: bool = field(
        default_factory=lambda: os.environ.get("DCP_DEMO", "0") == "1"
    )
    # Off by default: analysis writes project_status.md into every project.
    auto_analyze: bool = field(
        default_factory=lambda: os.environ.get("DCP_AUTO_ANALYZE", "0") == "1"
    )

    # "cli" runs agent_cmd; "native" uses the built-in LLM tool loop.
    agent_mode: str = field(
        default_factory=lambda: os.environ.get("DCP_AGENT_MODE", "cli")
    )
    agent_timeout: int = field(
        default_factory=lambda: int(os.environ.get("DCP_AGENT_TIMEOUT", "900"))
    )
    autopilot_workers: int = field(
        default_factory=lambda: int(os.environ.get("DCP_AUTOPILOT_WORKERS", "1"))
    )

    # Confidence decay: stage confidence halves after this many idle days.
    confidence_half_life_days: float = field(
        default_factory=lambda: float(os.environ.get("DCP_HALF_LIFE_DAYS", "14"))
    )

    # File the Settings UI persists LLM config to (also read on startup).
    env_file: str = field(
        default_factory=lambda: os.environ.get(
            "DCP_ENV_FILE", str(Path.cwd() / ".env")
        )
    )

    @property
    def web_dir(self) -> Path:
        return Path(__file__).parent / "interfaces" / "web"


def get_settings() -> Settings:
    """Load .env (real env vars win), then build Settings from the environment."""
    from dcp.envfile import load_env_file

    load_env_file(Path(os.environ.get("DCP_ENV_FILE", Path.cwd() / ".env")))
    return Settings()
