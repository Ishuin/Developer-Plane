"""Agent interface (template-method pattern)."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AgentUnavailable(RuntimeError):
    """Raised when an agent's dependencies or credentials are missing."""


class AgentResult(BaseModel):
    agent: str
    summary: str
    recommendations: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class Agent(ABC):
    name: str = "agent"
    tier: int = 0  # 0 = deterministic/offline, 1 = LLM-backed
    description: str = ""

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> AgentResult:
        """Execute against an assembled project context payload."""
